"""§17 Per-Lab Data Export / §18 Per-Lab Backup and Restore.

One shared bundle format backs both features (export is just "a backup
you download yourself instead of the system keeping it"): a versioned
JSON document covering every tenant-scoped table §17 lists explicitly
(Members, platform associations, Semesters, Challenges, Progress,
Reports, reminder history) plus the automation history tables scoped to
that tenant (sync_logs, job_run_logs). Encrypted credentials
(Platform.auth_config, Tenant.smtp_config) are deliberately never
included — restoring a Lab always starts with those unset, requiring
fresh credentials to be entered, per §17/§18's "exclude encrypted
credentials by default."

Executed synchronously (see TenantDataJob's own docstring for why that's
a reasonable v1 choice, not a shortcut nobody considered).
"""
import uuid
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import enable_email_lookup_now, enable_super_admin_now, enable_tenant_context_now
from app.models.challenge import Challenge
from app.models.job_run_log import JobRunLog
from app.models.member import Member
from app.models.member_platform_account import MemberPlatformAccount
from app.models.platform import Platform
from app.models.progress import Progress
from app.models.reminder_log import ReminderLog
from app.models.report import Report
from app.models.semester import Semester
from app.models.sync_log import SyncLog
from app.models.tenant import Tenant

BUNDLE_FORMAT_VERSION = "1"


class RestoreError(Exception):
    pass


def _json_safe(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _dump_rows(rows, fields: list[str]) -> list[dict]:
    return [{f: _json_safe(getattr(row, f)) for f in fields} for row in rows]


def export_tenant_bundle(db: Session, tenant: Tenant) -> dict:
    """Read-only — safe to call from either the Lab-Leader self-export
    endpoint or the Super Admin one. `db` must already be bound to
    `tenant.id`'s context (a Lab Leader's own request session already is;
    the Super Admin export endpoint binds it explicitly first)."""
    members = db.query(Member).filter(Member.tenant_id == tenant.id).all()
    member_ids = [m.id for m in members]
    semesters = db.query(Semester).filter(Semester.tenant_id == tenant.id).all()
    challenges = db.query(Challenge).filter(Challenge.tenant_id == tenant.id).all()
    challenge_ids = [c.id for c in challenges]
    platforms = db.query(Platform).filter(Platform.tenant_id == tenant.id).all()
    platform_accounts = (
        db.query(MemberPlatformAccount).filter(MemberPlatformAccount.member_id.in_(member_ids)).all()
        if member_ids
        else []
    )
    progress_rows = (
        db.query(Progress).filter(Progress.challenge_id.in_(challenge_ids)).all() if challenge_ids else []
    )
    reminder_logs = (
        db.query(ReminderLog).filter(ReminderLog.challenge_id.in_(challenge_ids)).all() if challenge_ids else []
    )
    reports = db.query(Report).filter(Report.tenant_id == tenant.id).all()
    sync_logs = db.query(SyncLog).filter(SyncLog.tenant_id == tenant.id).all()
    job_run_logs = db.query(JobRunLog).filter(JobRunLog.tenant_id == tenant.id).all()

    return {
        "format_version": BUNDLE_FORMAT_VERSION,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "tenant": {
            "id": str(tenant.id),
            "name": tenant.name,
            "slug": tenant.slug,
            "professor_email": tenant.professor_email,
            # smtp_config deliberately excluded (encrypted credential).
        },
        "members": _dump_rows(members, ["id", "full_name", "email", "role", "active", "joined_at"]),
        "platforms": _dump_rows(
            platforms, ["id", "name", "adapter_type", "base_url", "is_focus", "is_active"]
            # auth_config / credentials_verified_at deliberately excluded.
        ),
        "member_platform_accounts": _dump_rows(
            platform_accounts, ["id", "member_id", "platform_id", "external_username", "external_user_id"]
        ),
        "semesters": _dump_rows(semesters, ["id", "name", "start_date", "end_date", "is_current"]),
        "challenges": _dump_rows(
            challenges,
            [
                "id", "semester_id", "platform_id", "week_number", "title", "category", "difficulty",
                "external_challenge_id", "external_url", "presenter_id", "deadline_at", "points",
            ],
        ),
        "progress": _dump_rows(
            progress_rows, ["id", "member_id", "challenge_id", "status", "completed_at", "detected_by", "note"]
        ),
        "reports": _dump_rows(
            reports,
            [
                "id", "semester_id", "type", "period_start", "period_end", "generated_at", "status",
                "content", "approved_by", "sent_at", "recipient_email", "data",
            ],
        ),
        "reminder_logs": _dump_rows(reminder_logs, ["id", "challenge_id", "member_id", "milestone", "sent_at", "channel"]),
        "sync_logs": _dump_rows(
            sync_logs,
            ["id", "platform_id", "run_at", "status", "members_checked", "errors", "updated_count", "conflicts_count"],
        ),
        "job_run_logs": _dump_rows(job_run_logs, ["id", "job_type", "run_at", "status", "detail"]),
    }


def _parse_dt(value):
    return datetime.fromisoformat(value) if value else None


def _parse_date(value):
    return date.fromisoformat(value) if value else None


def restore_tenant_bundle(
    db: Session, bundle: dict, mode: str, target_tenant_id: uuid.UUID | None = None
) -> tuple[uuid.UUID, list[str]]:
    """§18 restore. mode="new_lab" creates a fresh Tenant with fresh IDs
    throughout (remapping every FK); mode="overwrite_existing" deletes
    `target_tenant_id`'s current data first (same DELETE FROM tenants
    path §16 uses, cascade + RLS bypass) then re-imports into a Tenant
    with that same ID. Either way, a Member email that already belongs to
    a DIFFERENT Tenant is skipped (not overwritten, not erroring the
    whole restore) — see the module docstring for why silent skip-with-
    warning was chosen over a harder failure mode.

    Takes the CALLER's `db` session (the admin endpoint's own, already
    Super-Admin-authenticated) rather than opening a second, independent
    one: a separate SessionLocal() here would be a second real Postgres
    connection doing large writes alongside whatever the request's own
    session is doing, with no shared transaction — harder to reason
    about, and not how any other service function in this codebase works
    (every one of them takes `db` as a parameter). Every RLS context this
    function needs is applied one-shot (SET LOCAL, current transaction
    only), freshly after each commit below — see enable_tenant_context_now's
    docstring for why the sticky bind_* helpers don't fit a
    multi-commit-from-here function called mid-request.

    Returns (new_or_target_tenant_id, warnings).
    """
    if bundle.get("format_version") != BUNDLE_FORMAT_VERSION:
        raise RestoreError(f"Unsupported bundle format_version {bundle.get('format_version')!r}")
    if mode not in ("new_lab", "overwrite_existing"):
        raise RestoreError(f"Unknown restore mode {mode!r}")

    warnings: list[str] = []
    from sqlalchemy import text

    tenant_data = bundle["tenant"]

    if mode == "overwrite_existing":
        if not target_tenant_id:
            raise RestoreError("overwrite_existing requires target_tenant_id")
        existing = db.get(Tenant, target_tenant_id)
        if not existing:
            raise RestoreError(f"Tenant {target_tenant_id} not found")
        new_slug = existing.slug  # read BEFORE deleting — the row (and this expired ORM object) is gone right after
        enable_super_admin_now(db)
        db.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": str(target_tenant_id)})
        db.commit()
        new_tenant_id = target_tenant_id
    else:
        new_tenant_id = uuid.uuid4()
        base_slug = tenant_data["slug"]
        new_slug = base_slug
        suffix = 1
        while db.query(Tenant).filter(Tenant.slug == new_slug).first():
            suffix += 1
            new_slug = f"{base_slug}-restored-{suffix}"

    db.add(
        Tenant(
            id=new_tenant_id,
            name=tenant_data["name"],
            slug=new_slug,
            professor_email=tenant_data.get("professor_email"),
        )
    )
    db.commit()

    enable_tenant_context_now(db, new_tenant_id)
    # Cross-tenant duplicate check needs to see every tenant's Members,
    # not just this new one's (empty so far anyway) — same narrow bypass
    # login/create_lab use for the identical reason.
    enable_email_lookup_now(db)
    # Email is globally unique at the DB level (see Member.email), so this
    # correctly catches BOTH a genuinely unrelated Tenant already using
    # the address AND the common case of restoring "new_lab" while the
    # original source Tenant this bundle came from is still alive (its
    # Members' emails are still legitimately taken) — "new_lab" restore
    # only fully succeeds member-for-member once the source is actually
    # gone (the disaster-recovery case), which matches reality: you can't
    # have two live accounts with the same email regardless of Tenant.
    member_id_map: dict[str, uuid.UUID] = {}
    for m in bundle["members"]:
        conflict = db.query(Member).filter(Member.email == m["email"], Member.tenant_id != new_tenant_id).first()
        if conflict:
            warnings.append(f"Skipped member {m['email']} — email already in use by another Lab")
            continue
        new_id = uuid.uuid4()
        member_id_map[m["id"]] = new_id
        db.add(
            Member(
                id=new_id,
                tenant_id=new_tenant_id,
                full_name=m["full_name"],
                email=m["email"],
                password_hash=hash_password(uuid.uuid4().hex),  # unusable random password — see the warning appended below
                role=m["role"],
                active=m["active"],
            )
        )
    db.commit()

    enable_tenant_context_now(db, new_tenant_id)
    platform_id_map: dict[str, uuid.UUID] = {}
    for p in bundle["platforms"]:
        new_id = uuid.uuid4()
        platform_id_map[p["id"]] = new_id
        db.add(
            Platform(
                id=new_id, tenant_id=new_tenant_id, name=p["name"], adapter_type=p["adapter_type"],
                base_url=p.get("base_url"), is_focus=p["is_focus"], is_active=p["is_active"],
                auth_config=None,  # never restored — re-enter credentials after restore
            )
        )
    db.commit()

    enable_tenant_context_now(db, new_tenant_id)
    for acc in bundle["member_platform_accounts"]:
        member_id = member_id_map.get(acc["member_id"])
        platform_id = platform_id_map.get(acc["platform_id"])
        if not member_id or not platform_id:
            continue
        db.add(
            MemberPlatformAccount(
                id=uuid.uuid4(), member_id=member_id, platform_id=platform_id,
                external_username=acc["external_username"], external_user_id=acc["external_user_id"],
            )
        )
    db.commit()

    enable_tenant_context_now(db, new_tenant_id)
    semester_id_map: dict[str, uuid.UUID] = {}
    for s in bundle["semesters"]:
        new_id = uuid.uuid4()
        semester_id_map[s["id"]] = new_id
        db.add(
            Semester(
                id=new_id, tenant_id=new_tenant_id, name=s["name"],
                start_date=_parse_date(s["start_date"]), end_date=_parse_date(s["end_date"]),
                is_current=s["is_current"],
            )
        )
    db.commit()

    enable_tenant_context_now(db, new_tenant_id)
    challenge_id_map: dict[str, uuid.UUID] = {}
    for c in bundle["challenges"]:
        semester_id = semester_id_map.get(c["semester_id"])
        platform_id = platform_id_map.get(c["platform_id"])
        if not semester_id or not platform_id:
            warnings.append(f"Skipped challenge {c.get('title')!r} — missing semester/platform mapping")
            continue
        new_id = uuid.uuid4()
        challenge_id_map[c["id"]] = new_id
        db.add(
            Challenge(
                id=new_id, tenant_id=new_tenant_id, semester_id=semester_id, platform_id=platform_id,
                week_number=c["week_number"], title=c["title"], category=c.get("category"),
                difficulty=c.get("difficulty"), external_challenge_id=c.get("external_challenge_id"),
                external_url=c.get("external_url"),
                presenter_id=member_id_map.get(c.get("presenter_id")), deadline_at=_parse_dt(c["deadline_at"]),
                points=c.get("points"),
            )
        )
    db.commit()

    enable_tenant_context_now(db, new_tenant_id)
    for p in bundle["progress"]:
        member_id = member_id_map.get(p["member_id"])
        challenge_id = challenge_id_map.get(p["challenge_id"])
        if not member_id or not challenge_id:
            continue
        db.add(
            Progress(
                id=uuid.uuid4(), member_id=member_id, challenge_id=challenge_id, status=p["status"],
                completed_at=_parse_dt(p.get("completed_at")), detected_by=p["detected_by"], note=p.get("note"),
            )
        )
    db.commit()

    enable_tenant_context_now(db, new_tenant_id)
    for r in bundle["reminder_logs"]:
        member_id = member_id_map.get(r["member_id"])
        challenge_id = challenge_id_map.get(r["challenge_id"])
        if not member_id or not challenge_id:
            continue
        db.add(
            ReminderLog(
                id=uuid.uuid4(), member_id=member_id, challenge_id=challenge_id, milestone=r["milestone"],
                channel=r["channel"],
            )
        )
    db.commit()

    enable_tenant_context_now(db, new_tenant_id)
    for r in bundle["reports"]:
        semester_id = semester_id_map.get(r["semester_id"])
        if not semester_id:
            warnings.append(f"Skipped a {r.get('type')} report — missing semester mapping")
            continue
        db.add(
            Report(
                id=uuid.uuid4(), tenant_id=new_tenant_id, semester_id=semester_id, type=r["type"],
                period_start=_parse_date(r["period_start"]), period_end=_parse_date(r["period_end"]),
                generated_at=_parse_dt(r.get("generated_at")), status=r["status"], content=r.get("content"),
                approved_by=r.get("approved_by"), sent_at=_parse_dt(r.get("sent_at")),
                recipient_email=r.get("recipient_email"), data=r.get("data"),
            )
        )
    db.commit()

    enable_tenant_context_now(db, new_tenant_id)
    for s in bundle["sync_logs"]:
        platform_id = platform_id_map.get(s["platform_id"])
        if not platform_id:
            continue
        db.add(
            SyncLog(
                id=uuid.uuid4(), tenant_id=new_tenant_id, platform_id=platform_id, status=s["status"],
                members_checked=s["members_checked"], errors=s.get("errors"),
                updated_count=s.get("updated_count", 0), conflicts_count=s.get("conflicts_count", 0),
            )
        )
    for j in bundle["job_run_logs"]:
        db.add(
            JobRunLog(id=uuid.uuid4(), tenant_id=new_tenant_id, job_type=j["job_type"], status=j["status"], detail=j.get("detail"))
        )
    db.commit()

    if member_id_map:
        warnings.append(
            "Restored accounts have a random, unusable password — use forgot-password (or a Super Admin "
            "Lab-Leader-recovery action) to regain access; original passwords are never included in a bundle."
        )
    return new_tenant_id, warnings
