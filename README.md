# HSLab CTF Classroom

Multi-tenant CTF progress management for HSLab. See `draft/HSLab_CTF_Classroom_PRD.md`
for the full product spec — this README covers **running and deploying** what's built
so far: Phase 0 (infra + DB schema), Phase 1 (multi-tenant auth, Super Admin console,
Member/Semester/Challenge CRUD, manual progress, dashboards), Phase 2 (Root Me adapter,
encrypted Platform credentials, manual sync), Phase 3 (scheduled sync across every Lab,
shared rate limiting), Phase 4 (T-3/T-1 reminders, weekly report generation, the
professor email draft/approve flow), Phase 5 (semester report — per-member ranking,
platform-switch-aware weekly trend, PDF/Excel export).

Stack: FastAPI (Python) + PostgreSQL backend, Next.js (TypeScript/Tailwind) frontend,
Celery + Redis for scheduled sync, PM2 + Cloudflare Tunnel for deployment on a WSL
machine with no static IP/domain.

---

## 1. One-time machine setup

### 1.1 PostgreSQL

```bash
sudo apt-get update && sudo apt-get install -y postgresql postgresql-contrib
sudo service postgresql start
sudo -u postgres psql -c "CREATE USER hslab WITH PASSWORD '<pick-a-password>';"
sudo -u postgres psql -c "CREATE DATABASE hslab_ctf OWNER hslab;"
```

WSL has no systemd service manager for postgres by default the way a real VM does —
`sudo service postgresql start` needs to be run again after every WSL restart unless
you enable systemd (see §4 below, which this project's PM2 setup already relies on).
With systemd enabled, `sudo systemctl enable postgresql` makes it start automatically.

### 1.2 Redis (Celery broker + shared rate limiter)

```bash
sudo apt-get install -y redis-server
sudo systemctl enable --now redis-server
redis-cli ping   # should print PONG
```

### 1.3 PM2 and cloudflared

```bash
# PM2 (via Node/npm, already required for the frontend)
npm install -g pm2

# cloudflared (Cloudflare Tunnel client)
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb
```

### 1.4 Backend Python environment

```bash
cd backend
python3 -m venv venv   # if this fails with "ensurepip is not available", either
                        # `sudo apt-get install python3-venv` or fall back to:
                        # pip3 install --user virtualenv && python3 -m virtualenv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 1.5 Frontend dependencies

```bash
cd frontend
npm install
```

---

## 2. Configure `.env`

Copy the template and fill in real values:

```bash
cp .env.example .env
```

Required keys (see comments in `.env.example` for details):

| Key | Purpose |
|---|---|
| `DATABASE_URL` | `postgresql://hslab:<password>@localhost:5432/hslab_ctf` |
| `JWT_SECRET_KEY` | random secret — generate with `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `SUPER_ADMIN_BOOTSTRAP_EMAIL` / `SUPER_ADMIN_BOOTSTRAP_PASSWORD` | one-time bootstrap for the first Super Admin account (§3.4) |
| `PLATFORM_SECRET_KEY` | Fernet key encrypting Platform API keys at rest — generate with `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Losing/rotating this makes existing saved credentials undecryptable — treat like `JWT_SECRET_KEY`. |
| `REDIS_URL` | `redis://localhost:6379/0` — Celery broker/backend and the shared Root Me rate limiter |
| `ROOTME_RATE_LIMIT_CAPACITY` / `ROOTME_RATE_LIMIT_REFILL_PER_SECOND` | shared token-bucket limit for every Root Me API call system-wide (Root Me rate-limits by IP, not per key) — conservative defaults, tune from observed 429s |
| `SYNC_INTERVAL_MINUTES` | how often the scheduled sync runs across all Labs (default 1440 = daily) |
| `REMINDER_CHECK_HOUR_UTC` | UTC hour (0-23) the daily T-3/T-1 reminder check runs |
| `WEEKLY_REPORT_DAY_OF_WEEK` / `WEEKLY_REPORT_HOUR_UTC` | when the weekly report draft is generated (default: Monday 00:00 UTC) |
| `DEFAULT_SMTP_HOST` etc. | system-default SMTP, used for any Lab that hasn't configured its own under Settings — leave `DEFAULT_SMTP_HOST` empty to require every Lab to configure SMTP itself |
| `CLOUDFLARE_TUNNEL_TOKEN` | leave empty for Quick Tunnel; fill in to switch to Named Tunnel (§6) |

`.env` is git-ignored and never committed. `.env.example` has no real values and is safe to commit.

---

## 3. First-time database setup

```bash
cd backend
source venv/bin/activate

# Create all tables
alembic upgrade head

# Create the first Super Admin account (reads SUPER_ADMIN_BOOTSTRAP_* from .env)
python -m app.seed_super_admin
```

Log in to the Super Admin console (`/console/login`) with those credentials, then use
it to create your first Lab + Lab Leader (§6.1 of the PRD). Everything else (members,
semesters, challenges) is managed from inside that Lab's own dashboard.

---

## 4. Enable auto-restart on WSL restart

This machine already has `systemd=true` set in `/etc/wsl.conf`, which is what makes
`pm2 startup` work at all under WSL2 — without it you'd need a fallback like a
`~/.bashrc` resurrect hook or a Windows Task Scheduler entry instead.

```bash
pm2 startup   # prints a systemd command — copy/paste and run exactly what it prints
pm2 save      # after starting the 3 processes below, snapshot them for the above to restore
```

---

## 5. Running the app (PM2)

Build the frontend once before starting in production mode (re-run after every
`git pull` / code change):

```bash
cd frontend && npm run build
```

Start all three processes from the project root:

```bash
pm2 start ecosystem.config.js
pm2 save   # persist this process list so `pm2 startup`'s systemd unit restores it
```

This starts exactly 3 named PM2 processes (updated from 2 in Phase 0's original §3.6 —
that section was written before Celery was in scope; the "no global commands" rule
below applies equally to all three):

- **`hslab-app`** — the whole app stack (FastAPI backend + Next.js frontend) as one
  PM2-managed process (see `scripts/start-app.sh`).
- **`hslab-tunnel`** — Cloudflare Tunnel, exposing the app at a public HTTPS URL
  (see `scripts/start-tunnel.sh`).
- **`hslab-celery`** — Celery worker with an embedded beat scheduler, running the
  scheduled sync loop across every Lab (see `scripts/start-celery.sh` and §11 below).

### ⚠️ This machine runs other PM2 processes unrelated to this project

**Never** run a PM2 command that targets "all" processes — `pm2 stop all`,
`pm2 delete all`, `pm2 restart all`, or `pm2 kill`. These affect every process PM2
manages, including ones that have nothing to do with this project. Always target
processes by their exact name:

```bash
# Status of just these three processes
pm2 list                       # shows all processes, but only touch hslab-*

# Individual process control — always by name, never "all"
pm2 restart hslab-app
pm2 restart hslab-tunnel
pm2 restart hslab-celery
pm2 stop hslab-app
pm2 stop hslab-tunnel
pm2 stop hslab-celery
pm2 start hslab-app
pm2 start hslab-tunnel
pm2 start hslab-celery

# Logs — per process
pm2 logs hslab-app
pm2 logs hslab-tunnel
pm2 logs hslab-celery
```

---

## 6. Finding your current Quick Tunnel URL

By default (no `CLOUDFLARE_TUNNEL_TOKEN` in `.env`), the tunnel runs in **Quick
Tunnel** mode: a free `*.trycloudflare.com` URL that Cloudflare generates fresh
**every time `hslab-tunnel` restarts** — there's no fixed address to bookmark.

To find the current URL:

```bash
./scripts/get-tunnel-url.sh
```

This greps `logs/hslab-tunnel.log` (where cloudflared prints it on startup) for the
most recent `https://*.trycloudflare.com` line. If the process just restarted, wait a
few seconds for cloudflared to connect and print the new URL.

---

## 7. Upgrading to a Named Tunnel (fixed domain)

Quick Tunnels are fine for short-lived testing but inconvenient for regular use since
the URL changes on every restart. To switch to a **Named Tunnel** with a fixed domain:

1. In the Cloudflare Zero Trust dashboard, create a Tunnel under **Networks → Tunnels**
   and connect it to a domain/subdomain you control.
2. Copy the tunnel token it gives you.
3. Put it in `.env`:
   ```
   CLOUDFLARE_TUNNEL_TOKEN=<your token>
   ```
4. Restart the tunnel process:
   ```bash
   pm2 restart hslab-tunnel
   ```

No code changes needed — `scripts/start-tunnel.sh` detects `CLOUDFLARE_TUNNEL_TOKEN`
in `.env` and automatically runs `cloudflared tunnel run --token ...` (Named Tunnel)
instead of `cloudflared tunnel --url ...` (Quick Tunnel).

---

## 8. Local development (without PM2)

For iterating on code, running the processes directly is faster than going through
PM2/build each time:

```bash
# Terminal 1 — backend, auto-reload
cd backend && source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend, dev server
cd frontend && npm run dev

# Terminal 3 — Celery worker + beat, only needed to test scheduled sync locally
cd backend && source venv/bin/activate
celery -A app.celery_app worker -B --loglevel=info
```

Then visit `http://localhost:3000`.

---

## 9. Scheduled sync (Celery)

Each active Lab's **focus Platform** (configured under Platforms in the Lab dashboard)
gets synced automatically on the interval set by `SYNC_INTERVAL_MINUTES` (default:
daily). A Lab is skipped — never errors the whole run — if its focus platform has no
credentials configured; this shows up on both that Lab's own dashboard and the Super
Admin console's "Labs needing attention" list.

Every Root Me API call, from anywhere in the app (scheduled sync *and* the manual
"Sync now" button in Platform Management), goes through one shared Redis-backed rate
limiter (`app/core/rate_limiter.py`) — Root Me limits by IP, not by api_key, so this
has to be global, not per-Lab. Tune `ROOTME_RATE_LIMIT_CAPACITY` /
`ROOTME_RATE_LIMIT_REFILL_PER_SECOND` in `.env` if you see 429s in practice.

To trigger a sync run immediately without waiting for the schedule (e.g. to test after
configuring a new Platform key):

```bash
cd backend && source venv/bin/activate
python -c "from app.tasks.sync_tasks import sync_all_tenants; sync_all_tenants.delay()"
```

Results land in `sync_log` (visible via each Lab's dashboard) — check `pm2 logs
hslab-celery` for task-level detail.

---

## 10. Reminders & weekly report (Celery)

**Reminders** (daily, `REMINDER_CHECK_HOUR_UTC`): for every Challenge, checks the T-3
and T-1 day-before-deadline milestones and emails any Member who hasn't completed it
(no Progress row, or status `missing`/`late`) directly — no draft/approve step, since
this is internal to the Lab, not communication leaving it. Each Member+Challenge+
milestone is only ever sent once (tracked in `reminder_log`).

**Weekly report** (`WEEKLY_REPORT_DAY_OF_WEEK`/`WEEKLY_REPORT_HOUR_UTC`, default Monday
00:00 UTC): generates one draft `Report` per active Lab aggregating last calendar
week's Done/Late/Missing counts and this week's Early list, rendered through
`app/templates/weekly_report_email.txt.j2`. **Sends nothing** — Lab Leaders review and
edit the draft under Reports in the dashboard, then Approve & Send (SMTP, per-Lab
config under Settings, with a system-default fallback — see `.env`).

Both need SMTP configured (Settings → SMTP, per-Lab, or `DEFAULT_SMTP_HOST` etc. as a
system-wide fallback) — use "Send a test email" under Settings to verify before relying
on it.

To trigger either immediately for testing:

```bash
cd backend && source venv/bin/activate
python -c "from app.tasks.reminder_tasks import check_reminders; check_reminders.delay()"
python -c "from app.tasks.report_tasks import generate_weekly_reports; generate_weekly_reports.delay()"
```

Or, per-Lab, from the dashboard: the Reports page has a "Generate now" button (Lab
Leader only) for testing without waiting for Monday.

---

## 11. Semester report

Manual only — from Semesters, a Lab Leader clicks "Generate Report" on any semester
(there's no automatic trigger on `end_date`; closing out a semester is an
administrative decision). Produces a draft `Report` (type=`semester`) covering the
whole semester: per-member Done/Late/Missing + cumulative points (our own
`Challenge.points`, not Root Me's global score) + internal ranking, and a lab-wide
completion trend grouped by `Challenge.week_number` (not calendar weeks — a different
grouping than the weekly report, on purpose).

If a semester's challenges span more than one focus Platform (a Lab can switch focus
mid-semester), the report calls that out explicitly — a warning banner, each week/
challenge's Platform labeled, and per-member stats broken out per-Platform — so
completion/points from two different platforms are never silently compared as one
continuous scale.

Same draft/approve/send pipeline as the weekly report (§10) — nothing new to learn
there. What's new: **Export PDF / Export Excel** buttons on any semester report (draft
or sent) render the underlying data (captured once at generation time, in `Report.data`
— exports stay consistent with what was reviewed even if newer sync data lands later)
into a file on demand. No new system dependency — both `reportlab` (PDF) and
`openpyxl` (Excel) are pure-Python, installed via `pip` like everything else in
`requirements.txt`.

---

## 12. Project layout

```
backend/    FastAPI app, SQLAlchemy models, Alembic migrations, Celery app + tasks,
            Root Me adapter (app/adapters/), shared rate limiter (app/core/rate_limiter.py),
            email/report/reminder services (app/services/), email templates (app/templates/)
frontend/   Next.js app (App Router) — Lab login, Lab dashboard, Super Admin console
scripts/    start-app.sh, start-tunnel.sh, start-celery.sh, get-tunnel-url.sh (used by PM2)
draft/      PRD and design source — not part of the running app
ecosystem.config.js   PM2 process definitions (hslab-app, hslab-tunnel, hslab-celery)
```

## 13. Roles

| Role | Where it logs in | Scope |
|---|---|---|
| Super Admin | `/console/login` | Whole system — create/suspend Labs |
| Lab Leader | `/login` | One Lab — full CRUD on that Lab's members/semesters/challenges/progress |
| Presenter | `/login` | One Lab — same Member/Semester/Challenge visibility as members, plus can record progress |
| Member | `/login` | One Lab — read-only view of members/semesters/challenges/progress |

---

## 14. UI design (current state)

This section exists so the current design can be handed to another design-focused
session for review/iteration — it describes what's actually built in `frontend/`, not
aspiration. Design source of truth: `draft/HSLab CTF Classroom v2.dc.html` (a static
HTML mockup, referenced from PRD §10) plus whatever the tables below add on top of it.
If you're revising this design, treat this section as the spec to update afterward —
implementation should follow it, not the other way around.

**Stack**: Next.js 16 (App Router) + React 19 + Tailwind CSS v4 (CSS-variable-based
theming via `@theme inline`, not the old `tailwind.config.js` approach) + Geist Sans /
Geist Mono (Google Fonts via `next/font`). No component library (no shadcn/radix) — a
small hand-rolled `components/ui/` kit, styled directly with Tailwind utility classes
plus CSS custom properties for anything themeable.

### 14.1 Two visual modes, deliberately distinct

The app has exactly two "skins," switched by a wrapping class, never by prop-drilling a
theme value:

| Mode | Where | Feel | Why |
|---|---|---|---|
| **Lab dashboard** | `/dashboard/*` | Light, teal accent (`#0d7d8f`) | A Lab Leader/Member's normal working view |
| **Super Admin console** | `/console/*` | Dark neutral (`#18181b` bg), **no accent color** | So "operating the whole system" never looks or feels like "managing one Lab" — a deliberate PRD §10 decision, not an oversight |

The console theme is applied via a single `.console-theme` class on the root div in
`app/console/layout.tsx`, which redefines the same CSS variables the light theme
uses (`--background`, `--surface`, `--foreground`, `--muted`, `--border`, `--accent`) —
every component in `components/ui/` reads only those variables, so no component has
mode-specific code.

### 14.2 Color tokens (`app/globals.css`)

```
--background:  #f7f9f9   page background
--surface:     #ffffff   card/input background
--foreground:  #101619   primary text
--muted:       #5d666d   secondary text
--border:      #e4e8e9   borders/dividers
--accent:      #0d7d8f   primary action color (teal)
--accent-foreground: #ffffff
```

Progress-status semantic colors (used by `StatusBadge` and status-colored text
throughout — these 4 states are a core domain concept, not just a badge style):

```
early   text #1d4ed8 / bg #e3ecfd   (blue)   — completed ahead of deadline
done    text #15803d / bg #e2f2e9   (green)  — completed on time
late    text #a16207 / bg #fbf0d8   (amber)  — completed after deadline
missing text #b91c1c / bg #fbe4e2   (red)    — not completed
```

Console theme overrides (same variable names, dark neutral, no accent):

```
--background: #18181b   --surface: #27272a   --foreground: #f4f4f5
--muted:      #a1a1aa   --border:  #3f3f46   --accent:     #52525b (grayscale, not teal)
```

### 14.3 Typography

- **Geist Sans** (`--font-sans`) — all UI text.
- **Geist Mono** (`--font-mono`, applied via a `.font-data` utility class) — reserved
  specifically for *numeric/data* values: dashboard stat counters, member counts,
  slugs. The intent is a visual cue that distinguishes "a number/code you might scan or
  copy" from prose, echoed from the design mockup.

### 14.4 Component kit (`frontend/components/ui/`)

Each is a thin wrapper: Tailwind utility classes + `cn()` (clsx + tailwind-merge) for
class overrides, `forwardRef` for form-library compatibility. No animation, no variant
library (no `class-variance-authority` usage despite it being a dependency — variants
are plain `Record<Variant, string>` lookup objects).

- **`Button`** — variants `default` (solid accent), `secondary` (border-gray fill),
  `outline` (bordered, transparent), `ghost` (no border/fill until hover), `destructive`
  (red, for delete-type actions). No `size` prop yet — one size everywhere.
- **`Card` / `CardHeader` / `CardTitle` / `CardContent`** — the single layout primitive
  the whole app is built from. Every page is Cards in a `space-y-*` stack or
  `grid grid-cols-*` row.
- **`Input`**, **`Label`**, **`Select`** — standard bordered form controls, focus ring
  in accent color at 50% opacity. No custom multi-select, date picker, or combobox —
  native `<input type="date">` etc. where needed.
- **`Badge`** — generic pill, neutral by default, callers pass status-specific text
  color via `className`.
- **`StatusBadge`** — the one domain-specific component: takes a `ProgressStatus`
  (`early`/`done`/`late`/`missing`) and renders the correct label + color pair from
  §14.2 automatically. Prefer this over raw `Badge` for anything progress-status
  related — it's the only place that mapping is allowed to live.

### 14.5 Layout patterns (consistent across every page)

- **Lab dashboard shell** (`app/dashboard/layout.tsx`): a single top header bar —
  small teal "tenant name" pill on the left (so the current Lab is always visible even
  though v1 is one-account-per-Lab), a horizontal pill-nav next to it (active route =
  solid accent background, inactive = muted text), signed-in member's name + role and
  a "Sign out" button on the right. Content area is centered, `max-w-5xl`.
- **Console shell** (`app/console/page.tsx`): no persistent nav at all — it's a single
  page (stat cards + a "Labs needing attention" alert card + a Labs table with an
  inline create-form), centered `max-w-4xl`. There's nothing else to navigate to yet.
- **List pages** (Members/Semesters/Challenges/Progress/Platforms/Reports): a Card
  containing a `<table>` (plain HTML table, styled via Tailwind, no data-grid library),
  with a "New X" button that toggles an inline create/edit `<form>` open inside the
  same Card rather than navigating to a separate route or opening a modal — there are
  **no modals anywhere in the app**.
- **Stat rows**: `grid grid-cols-3` (console) or `grid grid-cols-4` (Lab dashboard) of
  identical small Cards — muted label on top, large `.font-data` number below.
- **Alert/nudge cards**: a Card with a colored left/full border (`border-[var(--status-late)]`
  or `border-2 border-accent`) used sparingly for the small number of "this needs a
  human decision" states (weekly report awaiting approval, focus platform unconfigured,
  Labs needing attention) — deliberately the only cards in the app that visually
  stand out from the neutral gray-bordered default, so they don't get lost in a list of
  otherwise-equal stat cards.
- **Login pages** (`/login`, `/console/login`): centered single Card, `max-w-sm`, on a
  bare background — no header/nav chrome at all.

### 14.6 Page inventory (route → purpose)

```
/                          redirect/landing (not themed — check before reviewing)
/login                     Lab member login
/console/login             Super Admin login
/dashboard                 Lab overview: stat cards, status breakdown, sync status, nudges
/dashboard/members         Member CRUD (incl. external_user_id / Root Me id_auteur)
/dashboard/semesters       Semester CRUD + "Generate Report" entry point
/dashboard/challenges      Challenge CRUD (week_number, deadline, points, platform)
/dashboard/progress        Manual progress recording, filterable by semester/challenge
/dashboard/platforms       Platform credentials, focus platform, test-connection, sync-now
/dashboard/reports         Weekly + semester report list, draft review/edit/approve/send, PDF/Excel export
/dashboard/settings        SMTP config (per-Lab) + test email
/console                   Super Admin: system stats, Labs needing attention, Lab CRUD
```

### 14.7 What this design deliberately does *not* have (yet)

Worth stating explicitly so a design review isn't surprised by the absence: no dark
mode for the Lab dashboard (only the console is dark, and that's a fixed identity, not
a toggle), no mobile-specific layout (fixed `max-w-*` centered containers, not
responsive breakpoints), no modals/toasts (errors render as inline red text, not
dismissible popups), no icon set beyond `lucide-react` being an installed-but-largely-
unused dependency, no loading skeletons (pages render `null` until data arrives).
# ctf-management
