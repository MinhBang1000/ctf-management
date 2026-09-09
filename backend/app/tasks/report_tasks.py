from datetime import datetime, timezone

from app.models.report import Report
from app.models.semester import Semester
from app.services.notification_service import notify_lab_leaders


def notify_ended_semesters_without_a_report(db, tenant_id) -> None:
    """§12 — the persisted-notification version of the nudge
    /api/v1/dashboard has always computed live for its own banner (kept
    as-is; this doesn't replace that). dedupe=True (the default) means
    this only actually creates a notification the first time it notices
    a given Semester still has no report — it's safe to call on every
    dispatcher tick without spamming.

    Historically this lived alongside a `generate_weekly_reports` Celery
    beat task in this same module; that task (and reminder_tasks.py's
    `check_reminders`) was removed when scheduling moved from one
    system-wide .env-fixed cron to app.tasks.automation_dispatcher's
    per-Lab dynamic schedule — this helper is still called from there.
    """
    reported_semester_ids = {
        r.semester_id for r in db.query(Report.semester_id).filter(Report.tenant_id == tenant_id, Report.type == "semester")
    }
    ended = (
        db.query(Semester)
        .filter(Semester.tenant_id == tenant_id, Semester.end_date < datetime.now(timezone.utc).date())
        .all()
    )
    for semester in ended:
        if semester.id in reported_semester_ids:
            continue
        notify_lab_leaders(
            db,
            tenant_id,
            type="semester_report_nudge",
            title=f'"{semester.name}" ended with no semester report yet',
            body=f"Ended {semester.end_date} — generate one from Semesters.",
            target_type="semester",
            target_id=semester.id,
        )
