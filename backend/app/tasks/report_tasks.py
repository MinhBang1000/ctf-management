import logging

from app.celery_app import celery_app
from app.db.session import SessionLocal, tenant_session
from app.models.tenant import Tenant
from app.services.alerting_service import record_job_run
from app.services.report_service import generate_weekly_report_for_tenant

logger = logging.getLogger(__name__)


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
                    record_job_run(db, tenant_id, "weekly_report", success=True)
        except Exception:  # noqa: BLE001 - one tenant's failure must not stop the rest
            logger.exception("generate_weekly_reports failed for tenant %s", tenant_id)
            try:
                with tenant_session(tenant_id) as db:
                    record_job_run(db, tenant_id, "weekly_report", success=False, detail="unexpected task failure")
            except Exception:  # noqa: BLE001 - even recording the failure must not crash the loop
                logger.exception("Failed to record weekly_report failure for tenant %s", tenant_id)
