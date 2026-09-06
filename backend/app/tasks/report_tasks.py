import logging
from datetime import datetime, timezone

from app.celery_app import celery_app
from app.db.session import SessionLocal, tenant_session
from app.models.report import Report
from app.models.semester import Semester
from app.models.tenant import Tenant
from app.services.alerting_service import record_job_run
from app.services.notification_service import notify_lab_leaders
from app.services.report_service import generate_weekly_report_for_tenant

logger = logging.getLogger(__name__)


def _notify_ended_semesters_without_a_report(db, tenant_id) -> None:
    """§12 — the persisted-notification version of the nudge
    /api/v1/dashboard has always computed live for its own banner (kept
    as-is; this doesn't replace that). dedupe=True (the default) means
    this only actually creates a notification the first time it notices
    a given Semester still has no report — it's safe to call on every
    weekly run without spamming."""
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


@celery_app.task(name="app.tasks.report_tasks.generate_weekly_reports")
def generate_weekly_reports() -> None:
    """Celery beat entrypoint (PRD §6.8), weekly. Generates a draft Report
    per active Tenant — never sends anything (that's the approve flow).
    One Tenant's failure must not stop the others."""
    db = SessionLocal()
    try:
        tenant_ids = [t.id for t in db.query(Tenant).filter(Tenant.is_active.is_(True)).all()]
    finally:
        db.close()

    for tenant_id in tenant_ids:
        try:
            with tenant_session(tenant_id) as db:
                tenant = db.get(Tenant, tenant_id)
                if not tenant:
                    continue
                report = generate_weekly_report_for_tenant(db, tenant)
                if report is None:
                    # No Semester yet — a configuration-incomplete state,
                    # not a job failure (same reasoning as sync's
                    # "skipped_not_configured": already visible on the
                    # dashboard, doesn't need to also alert).
                    logger.info("No Semester for tenant %s, skipped weekly report", tenant_id)
                    record_job_run(db, tenant_id, "weekly_report", success=True, detail="skipped: no Semester")
                else:
                    if report.status == "draft":
                        # Only for a genuinely fresh/updated draft — not
                        # when generate_weekly_report_for_tenant's own
                        # idempotency (§9) returned an already-sent report
                        # untouched, which shouldn't re-notify anyone.
                        notify_lab_leaders(
                            db,
                            tenant_id,
                            type="report_ready",
                            title="Weekly report ready to review",
                            body=f"Week of {report.period_start} – {report.period_end}",
                            target_type="report",
                            target_id=report.id,
                        )
                    record_job_run(db, tenant_id, "weekly_report", success=True)
                _notify_ended_semesters_without_a_report(db, tenant_id)
                db.commit()
        except Exception:  # noqa: BLE001 - one tenant's failure must not stop the rest
            logger.exception("generate_weekly_reports failed for tenant %s", tenant_id)
            try:
                with tenant_session(tenant_id) as db:
                    record_job_run(db, tenant_id, "weekly_report", success=False, detail="unexpected task failure")
            except Exception:  # noqa: BLE001 - even recording the failure must not crash the loop
                logger.exception("Failed to record weekly_report failure for tenant %s", tenant_id)
