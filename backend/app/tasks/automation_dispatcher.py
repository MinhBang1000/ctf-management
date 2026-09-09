import logging
from datetime import datetime, timezone

from app.celery_app import celery_app
from app.db.session import SessionLocal, tenant_session
from app.models.report_send_attempt import ReportSendAttempt
from app.models.semester import Semester
from app.models.tenant import Tenant
from app.services.alerting_service import record_job_run
from app.services.automation_schedule import RepeatSchedule, is_due
from app.services.automation_settings_service import get_or_create_automation_settings
from app.services.email_service import EmailConfigError, EmailSendError, send_email
from app.services.notification_service import notify_lab_leaders
from app.services.reminder_service import send_reminders_for_tenant
from app.services.report_service import generate_semester_report_for_tenant, generate_weekly_report_for_tenant
from app.tasks.report_tasks import notify_ended_semesters_without_a_report

logger = logging.getLogger(__name__)

# Recorded as the actor on an auto-sent report's ReportSendAttempt /
# Report.approved_by — distinguishes "the dispatcher sent this with no
# human review" from an actual Lab Leader's email in that same column.
SYSTEM_AUTO_SEND_LABEL = "system:auto-send"


def _reminder_schedule(s) -> RepeatSchedule:
    return RepeatSchedule(
        enabled=s.reminder_enabled, repeat=s.reminder_repeat, time_of_day=s.reminder_time_of_day,
        day_of_week=s.reminder_day_of_week, day_of_month=s.reminder_day_of_month,
        interval_days=s.reminder_interval_days,
    )


def _weekly_report_schedule(s) -> RepeatSchedule:
    return RepeatSchedule(
        enabled=s.weekly_report_enabled, repeat=s.weekly_report_repeat, time_of_day=s.weekly_report_time_of_day,
        day_of_week=s.weekly_report_day_of_week, day_of_month=s.weekly_report_day_of_month,
        interval_days=s.weekly_report_interval_days,
    )


def _auto_send_report(db, report, tenant, kind: str = "initial") -> None:
    """The dispatcher's own send path — deliberately not shared code with
    reports.py's _send_and_record (different actor shape: no Member, this
    is a scheduled system action, not an HTTP request from a Lab Leader).
    Skips quietly (does not raise, does not block the rest of the tenant's
    automation) when there's nowhere configured to send to — a missing
    professor_email is a configuration gap the Lab Leader needs to fix,
    not a job failure.
    """
    to_address = tenant.professor_email
    if not to_address:
        logger.info("Auto-send skipped for tenant %s report %s: no professor_email configured", tenant.id, report.id)
        return
    report_label = "Semester Report" if report.type == "semester" else "Weekly Report"
    try:
        send_email(
            tenant, to_address,
            subject=f"{tenant.name} — {report_label} ({report.period_start} to {report.period_end})",
            body=report.content or "",
        )
    except (EmailConfigError, EmailSendError) as exc:
        db.add(ReportSendAttempt(
            report_id=report.id, recipient_email=to_address, kind=kind, status="failed",
            error_detail=str(exc), attempted_by_email=SYSTEM_AUTO_SEND_LABEL,
        ))
        db.commit()
        logger.warning("Auto-send failed for tenant %s report %s: %s", tenant.id, report.id, exc)
        return

    db.add(ReportSendAttempt(
        report_id=report.id, recipient_email=to_address, kind=kind, status="success",
        attempted_by_email=SYSTEM_AUTO_SEND_LABEL,
    ))
    report.recipient_email = to_address
    report.status = "sent"
    report.sent_at = datetime.now(timezone.utc)
    report.approved_by = SYSTEM_AUTO_SEND_LABEL
    db.commit()


def _dispatch_reminders(db, tenant, tenant_id, settings, now) -> None:
    if not is_due(_reminder_schedule(settings), now, settings.reminder_last_fired_at):
        return
    result = send_reminders_for_tenant(db, tenant, settings)
    settings.reminder_last_fired_at = now
    db.commit()
    if result["queued"]:
        notify_lab_leaders(
            db, tenant_id, type="reminders_ready",
            title=f"{len(result['queued'])} reminder(s) ready to review",
            body="Review and send them from Automation.",
            target_type="reminder", target_id=None,
        )
    record_job_run(
        db, tenant_id, "reminder", success=not result["errors"],
        detail="; ".join(result["errors"]) if result["errors"] else None,
    )


def _dispatch_weekly_report(db, tenant, tenant_id, settings, now) -> None:
    if not is_due(_weekly_report_schedule(settings), now, settings.weekly_report_last_fired_at):
        return
    report = generate_weekly_report_for_tenant(db, tenant)
    settings.weekly_report_last_fired_at = now
    db.commit()

    if report is None:
        # No Semester yet — configuration-incomplete, not a job failure
        # (same reasoning as sync's "skipped_not_configured").
        logger.info("No Semester for tenant %s, skipped weekly report", tenant_id)
        record_job_run(db, tenant_id, "weekly_report", success=True, detail="skipped: no Semester")
    else:
        if report.status == "draft":
            # §9 idempotency may have returned an already-sent report
            # untouched (e.g. schedule fired again before last_fired_at
            # got persisted) — only a genuinely fresh/updated draft gets
            # auto-sent or notified about.
            if settings.weekly_report_auto_send:
                _auto_send_report(db, report, tenant)
            else:
                notify_lab_leaders(
                    db, tenant_id, type="report_ready", title="Weekly report ready to review",
                    body=f"Week of {report.period_start} – {report.period_end}",
                    target_type="report", target_id=report.id,
                )
        record_job_run(db, tenant_id, "weekly_report", success=True)
    notify_ended_semesters_without_a_report(db, tenant_id)
    db.commit()


def _dispatch_semester_reports(db, tenant, tenant_id, now) -> None:
    """Single-date trigger, not a repeating schedule — fires at most once
    per Semester (report_last_fired_at gates it), even if
    report_trigger_date is in the past by the time automation is enabled
    or the dispatcher catches up after downtime."""
    due = (
        db.query(Semester)
        .filter(
            Semester.tenant_id == tenant_id,
            Semester.report_automation_enabled.is_(True),
            Semester.report_last_fired_at.is_(None),
            Semester.report_trigger_date <= now.date(),
        )
        .all()
    )
    for semester in due:
        report = generate_semester_report_for_tenant(db, tenant, semester)
        semester.report_last_fired_at = now
        db.commit()
        if report.status == "draft":
            if semester.report_auto_send:
                _auto_send_report(db, report, tenant)
            else:
                notify_lab_leaders(
                    db, tenant_id, type="report_ready", title="Semester report ready to review",
                    body=f"{semester.name} ({semester.start_date} – {semester.end_date})",
                    target_type="report", target_id=report.id,
                )
        record_job_run(db, tenant_id, "semester_report", success=True)
        db.commit()


@celery_app.task(name="app.tasks.automation_dispatcher.dispatch_automation")
def dispatch_automation() -> None:
    """Celery beat entrypoint, every DISPATCH_INTERVAL_SECONDS (short —
    a few minutes). Replaces the old system-wide, .env-fixed
    check-reminders/generate-weekly-reports crontab entries: each active
    Tenant now has its own schedule (TenantAutomationSettings), checked
    here via app.services.automation_schedule.is_due against that
    schedule's own last-fired anchor. One Tenant's failure must not stop
    the rest — same isolation shape as every other per-tenant Celery task
    in this codebase.
    """
    db = SessionLocal()
    try:
        tenant_ids = [t.id for t in db.query(Tenant).filter(Tenant.is_active.is_(True)).all()]
    finally:
        db.close()

    now = datetime.now(timezone.utc)
    for tenant_id in tenant_ids:
        try:
            with tenant_session(tenant_id) as db:
                tenant = db.get(Tenant, tenant_id)
                if not tenant:
                    continue
                settings = get_or_create_automation_settings(db, tenant_id)
                _dispatch_reminders(db, tenant, tenant_id, settings, now)
                _dispatch_weekly_report(db, tenant, tenant_id, settings, now)
                _dispatch_semester_reports(db, tenant, tenant_id, now)
        except Exception:  # noqa: BLE001 - one tenant's failure must not stop the rest
            logger.exception("dispatch_automation failed for tenant %s", tenant_id)
            try:
                with tenant_session(tenant_id) as db:
                    record_job_run(db, tenant_id, "automation_dispatch", success=False, detail="unexpected task failure")
            except Exception:  # noqa: BLE001 - even recording the failure must not crash the loop
                logger.exception("Failed to record dispatch failure for tenant %s", tenant_id)
