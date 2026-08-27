<title>HSLab CTF Classroom — Operations Guide</title>

This is the **running-the-application** guide — backups, alerting, and onboarding a
new Lab. For **process management** (PM2, Cloudflare Tunnel, first-time machine setup,
starting/stopping/restarting `hslab-app`/`hslab-tunnel`/`hslab-celery`), see
`README.md` instead. This document assumes that setup is already done.

---

## 1. Backups

### 1.1 Automated (full database)

A Celery beat task (`run_scheduled_backup`, part of the existing `hslab-celery`
process — no new PM2 process) runs `pg_dump -Fc` daily at `BACKUP_HOUR_UTC` (default
03:00 UTC), writing a timestamped, compressed dump to `BACKUP_DIR` (default
`./backups/`), and deletes anything older than the most recent `BACKUP_RETENTION_COUNT`
(default 14).

**Per-Lab granular backup/restore is explicitly not built for v1** — the shared-schema
multi-tenant design (every Lab's data lives in the same tables, distinguished by
`tenant_id`) makes true per-tenant backup genuinely complex for little real benefit at
this scale. Full-database backup, restorable as a whole, is the accepted answer. See
§1.3 for how to pull one Lab's data out of a full backup manually, if a Lab is ever
offboarded.

**Why a dedicated `hslab_backup` Postgres role exists, and why it matters:** the app's
own `DATABASE_URL` role (`hslab`) is deliberately kept subject to Row-Level Security
at all times — see §Row-Level-Security notes in the gotcha list (§4) for why. But a
`pg_dump` run by a role subject to RLS (specifically `FORCE ROW LEVEL SECURITY`,
which `hslab` has) with no tenant context set gets either a **filtered dump** or an
outright failure — either way, a backup that silently doesn't contain what you think
it does. `hslab_backup` is a separate, `BYPASSRLS`, read-only-grant role used *only*
for `pg_dump`, configured via `BACKUP_DATABASE_URL` — never the app's own runtime
connection. If this role doesn't exist yet, create it once:

```bash
sudo -u postgres psql -c "CREATE ROLE hslab_backup WITH LOGIN PASSWORD '<pick-a-password>' BYPASSRLS;"
sudo -u postgres psql -d hslab_ctf -c "GRANT CONNECT ON DATABASE hslab_ctf TO hslab_backup;"
sudo -u postgres psql -d hslab_ctf -c "GRANT USAGE ON SCHEMA public TO hslab_backup;"
sudo -u postgres psql -d hslab_ctf -c "GRANT SELECT ON ALL TABLES IN SCHEMA public TO hslab_backup;"
sudo -u postgres psql -d hslab_ctf -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO hslab_backup;"
```

Then set `BACKUP_DATABASE_URL=postgresql://hslab_backup:<password>@localhost:5432/hslab_ctf`
in `.env`.

To trigger a backup immediately (testing, or before a risky migration):

```bash
cd backend && source venv/bin/activate
python -c "from app.services.backup_service import run_backup; print(run_backup())"
```

### 1.2 Restore (full database)

```bash
# Stop the app first — restoring into a live database with active connections will fail/corrupt.
pm2 stop hslab-app hslab-celery   # by name only, never "all" — see README.md

# Drop and recreate the target database (DESTRUCTIVE — confirm you have the right dump first)
sudo -u postgres psql -c "DROP DATABASE hslab_ctf;"
sudo -u postgres psql -c "CREATE DATABASE hslab_ctf OWNER hslab;"

# Restore
pg_restore -h localhost -U hslab_backup -d hslab_ctf --no-owner backups/hslab_ctf_YYYYMMDD_HHMMSS.dump

pm2 start hslab-app hslab-celery
```

Note: restoring recreates all tables and RLS policies exactly as they were dumped
(RLS policy definitions are part of the schema, `pg_dump -Fc` includes them) — no
separate step needed to re-enable Row-Level Security after a restore.

### 1.3 Manual single-tenant export (Lab offboarding)

Not automated — a documented manual procedure is sufficient for v1, since Lab
offboarding is rare and deliberate, not something to build self-service tooling for.

1. Find the tenant's `id`:
   ```bash
   PGPASSWORD=... psql -h localhost -U hslab_backup -d hslab_ctf -c \
     "SELECT id, name, slug FROM tenants WHERE slug = '<lab-slug>';"
   ```
2. For each tenant-scoped table, export just that Lab's rows via `\copy` (client-side,
   works with any role that can `SELECT`, including `hslab_backup`):
   ```bash
   TENANT_ID='<uuid-from-step-1>'
   for table in members semesters challenges platforms reports sync_logs job_run_logs; do
     PGPASSWORD=... psql -h localhost -U hslab_backup -d hslab_ctf -c \
       "\copy (SELECT * FROM $table WHERE tenant_id = '$TENANT_ID') TO '${table}_export.csv' CSV HEADER"
   done
   # progress and reminder_logs have no direct tenant_id column — join through challenges:
   PGPASSWORD=... psql -h localhost -U hslab_backup -d hslab_ctf -c \
     "\copy (SELECT p.* FROM progress p JOIN challenges c ON c.id = p.challenge_id WHERE c.tenant_id = '$TENANT_ID') TO 'progress_export.csv' CSV HEADER"
   PGPASSWORD=... psql -h localhost -U hslab_backup -d hslab_ctf -c \
     "\copy (SELECT r.* FROM reminder_logs r JOIN challenges c ON c.id = r.challenge_id WHERE c.tenant_id = '$TENANT_ID') TO 'reminder_logs_export.csv' CSV HEADER"
   # member_platform_accounts scopes via members:
   PGPASSWORD=... psql -h localhost -U hslab_backup -d hslab_ctf -c \
     "\copy (SELECT mpa.* FROM member_platform_accounts mpa JOIN members m ON m.id = mpa.member_id WHERE m.tenant_id = '$TENANT_ID') TO 'member_platform_accounts_export.csv' CSV HEADER"
   ```
3. Hand the resulting CSVs to the Lab (or archive them, per your data-retention policy),
   then deactivate the Lab from the Super Admin console (`PATCH /admin/labs/{id}`) —
   this does **not** delete data, just suspends the Lab. Actual deletion isn't built
   (no destructive Lab-removal endpoint exists) — if a Lab genuinely needs its data
   erased, that's a manual `DELETE FROM tenants WHERE id = '...'` (cascades to every
   tenant-scoped table via the FK `ON DELETE CASCADE` chains) run directly against the
   database, deliberately outside the app, as a last-resort, closely-supervised action.

---

## 2. Alerting

Sync, reminder, and weekly-report jobs each track per-Tenant run history (`sync_log`
for sync, the new `job_run_log` table for the other two). When a Tenant hits
**`ALERT_FAILURE_THRESHOLD` (default 3) consecutive failures** for the same job type,
every active Super Admin gets an email — sent via the system-default SMTP
(`DEFAULT_SMTP_*`), deliberately never that Tenant's own SMTP config (using a possibly-
broken tenant SMTP to alert about that same tenant's failure would be circular). This
fires **once per failure streak**, not on every subsequent failed run — it resets once
that Tenant has a successful run again.

This is the *active* channel. The Super Admin console's "Labs needing attention" list
(built in Phase 3) is the *passive* one — check it any time, whether or not an alert
has fired. Both exist on purpose: the dashboard for browsing, the email for the case
where nobody happens to be looking at the dashboard.

**What "not configured yet" does NOT do:** a Lab that simply hasn't set up its
Platform/Semester yet shows as `skipped_not_configured` (sync) or a skip note (weekly
report) — this does **not** count toward the alert threshold. Only genuine failures
(a key that used to work and now doesn't, an SMTP send that's actually failing) do.
Otherwise every newly-created, not-yet-configured Lab would immediately start emailing
Super Admin, which isn't useful signal.

**Responding to an alert:**
1. Identify the Tenant and job type from the email subject.
2. Sync failures → check that Lab's Platform config (Platforms page → Test
   Connection) — most likely an expired/revoked Root Me key.
3. Reminder/weekly-report failures → check that Lab's SMTP config (Settings → Send a
   test email) — most likely expired credentials or a changed SMTP provider. If the
   *system default* SMTP is what's failing (a Lab using the fallback), check
   `DEFAULT_SMTP_*` in `.env` directly.
4. No automated re-alert will fire again until either it resolves (streak resets on a
   success) or continues (already flagged, silent until resolved) — no need to
   "acknowledge" anything, there's no alert-state to clear.

---

## 3. Onboarding a new Lab, end to end

This walks through everything built across all 6 phases, in the order a real Lab
onboarding actually happens.

1. **Super Admin creates the Lab** — System Console (`/console`) → New Lab. Enter the
   Lab's name, a URL-safe slug, and the first Lab Leader's name/email/temporary
   password. This also auto-seeds a "Root Me" Platform for the Lab (unconfigured,
   `is_focus=true`) so Challenge creation isn't blocked from day one.
2. **Lab Leader logs in** (`/login`, the email/password from step 1) and lands on
   their Lab's dashboard — it'll show a warning that the focus platform has no
   credentials yet.
3. **Configure the Platform** — Platforms page → Edit the seeded "Root Me" entry,
   paste in the Lab's own Root Me API key (get one by logging into a Root Me account
   the Lab controls, at `root-me.org/?page=preferences`) → **Test Connection** before
   relying on it. Once it passes, **Make Focus** becomes available (this is a
   deliberate, explicit action, not automatic).
4. **Create a Semester** — Semesters page → set start/end dates, mark it current.
5. **Add Members** — Members page → for each member, their Root Me *username* is
   optional/informational, but the Root Me *ID* (`id_auteur`) is **required** — use
   "Tra cứu ID" to look it up from the username (a convenience only; the Admin must
   still confirm the value before saving, it's never silently auto-filled).
6. **Create Challenges** — Challenges page → assign each to the current Semester and
   the (now-focused) Platform, with a deadline and a point value. Optionally fill in
   the Root Me challenge ID and use "Fetch from Root Me" to prefill the title/category.
7. **Automation now runs unattended**: sync (daily by default), T-3/T-1 reminders
   direct to Members, and a weekly report draft every Monday — all via the existing
   `hslab-celery` process, nothing further to start.
8. **Weekly report review** — Reports page, whenever a new draft shows up (also
   surfaced as a banner on the dashboard) → review/edit the generated content → set a
   recipient (pre-filled from Settings → Professor email, if set, but always
   explicitly confirmed at send time) → Approve & Send.
9. **End of semester** — Semesters page → Generate Report (manual only, never
   automatic — closing a semester is an administrative call) → same review/approve/
   send flow as the weekly report, plus Export PDF / Export Excel for anything needing
   a downloadable file (e.g. for an institution's own records).

---

## 4. Gotchas a future maintainer would otherwise rediscover the hard way

- **WSL + `pm2 startup` needs `systemd=true` in `/etc/wsl.conf`.** Without it, PM2
  auto-restart-on-reboot doesn't work at all under WSL2, and there's no clean error
  telling you why — see README.md §4.
- **The Root Me rate limiter's numbers (`ROOTME_RATE_LIMIT_CAPACITY=5`,
  `REFILL_PER_SECOND=1.0`) are an untested starting guess, not a measured limit.**
  Root Me publishes no documented rate limit. Reviewed at the end of Phase 6 against
  all accumulated `sync_log`/worker-log history: zero real evidence either way, since
  every sync in this environment has been 1 member with a test/expired key — there's
  never been real concurrent traffic to judge the defaults against. Revisit once a
  Lab has real member volume and you can observe actual 429 behavior.
- **Root Me's `validations[].date` is Europe/Paris local time (CET/CEST), not UTC** —
  confirmed via a real API call (not assumed): fetched a challenge's validations at a
  known server time and found entries timestamped *after* that time, which is only
  possible if the platform's own displayed time already carries a positive UTC
  offset. Converted via `zoneinfo.ZoneInfo("Europe/Paris")` on ingest (handles the
  CET/CEST DST boundary correctly year-round) — see `app/adapters/rootme.py`.
- **Root Me's JSON shapes are inconsistent across its own endpoints.** `/auteurs/{id}`
  returns `validations` as a real JSON array; `/challenges/{id}` and `/auteurs?nom=`
  both return list-like data as an object with numeric-string keys
  (`{"0": {...}, "1": {...}}`) instead. A zero-result search on `/auteurs?nom=` also
  returns HTTP 404, not an empty 200. None of this generalizes from one endpoint to
  another — each needed (and got) its own live verification before being trusted.
- **`Report.data` is a snapshot taken once at generation time, not a live query.**
  Semester report PDF/Excel exports render whatever was stored in this JSONB column
  when the report was generated — deliberately, so an export always matches what was
  actually reviewed/approved, even if newer sync/progress data lands afterward. If you
  need "current data as of right now," that's `POST /api/v1/reports/generate-now` or
  `POST /api/v1/semesters/{id}/generate-report` producing a *new* report, not
  re-exporting an old one.
- **Row-Level Security: `hslab` owns every table, so `FORCE ROW LEVEL SECURITY` is
  load-bearing, not optional.** Postgres doesn't apply RLS to a table's owner unless
  FORCE is set — without it, every policy below would be silently inert for the app's
  own connection. Relatedly:
  - **A custom Postgres GUC that's been `SET LOCAL` even once on a connection reverts
    to `''` (empty string) after that transaction, not `NULL`**, once the connection
    pool reuses it for a later, unrelated transaction. This broke the Super Admin
    dashboard in testing (`''::uuid` raising `invalid input syntax for type uuid`) —
    fixed with `NULLIF(current_setting(...), '')::uuid` in every RLS policy
    expression, not `current_setting(...)::uuid` directly.
  - **A one-time `SET LOCAL` per request is not enough if that request's session
    commits more than once** (e.g. `record_job_run` writes a row, commits, then
    queries again for the alert-threshold check) — `SET LOCAL` only lasts one
    transaction. Fixed by hooking SQLAlchemy's `after_begin` event
    (`app/db/session.py::bind_tenant_context` et al.) so the context re-applies on
    every transaction the session opens, not just the first.
  - **`pg_dump` and `FORCE ROW LEVEL SECURITY` conflict** — see §1.1 above.
  - Super Admin's RLS bypass is scoped per-table, per-operation (see the RLS
    migration's docstring, `alembic/versions/..._enable_row_level_security.py`) to
    match exactly what's confirmed necessary by code review — `members` in particular
    has **no** Super-Admin SELECT/UPDATE/DELETE bypass at all, enforcing "no
    impersonation" (PRD §9 item 6) at the database layer, not just the application
    layer.
