import logging

from app.celery_app import celery_app
from app.db.session import SessionLocal, tenant_session
from app.models.tenant import Tenant
from app.services.alerting_service import record_job_run
from app.services.reminder_service import send_reminders_for_tenant

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.reminder_tasks.check_reminders")
def check_reminders() -> None:
    """Celery beat entrypoint (PRD §6.7), daily. One Tenant's SMTP/email
    failure must not stop reminders for the rest — each tenant's errors
    are caught inside send_reminders_for_tenant and logged, never raised."""
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
                result = send_reminders_for_tenant(db, tenant)
                if result["errors"]:
                    logger.warning("Reminders for tenant %s had errors: %s", tenant_id, result["errors"])
                # Phase 6: reminders previously had no persisted per-run
                # history at all — this both closes that gap and feeds
                # the alerting threshold check.
                record_job_run(
                    db,
                    tenant_id,
                    "reminder",
                    success=not result["errors"],
                    detail="; ".join(result["errors"]) if result["errors"] else None,
                )
        except Exception:  # noqa: BLE001 - one tenant's failure must not stop the rest
            logger.exception("check_reminders failed for tenant %s", tenant_id)
            try:
                with tenant_session(tenant_id) as db:
                    record_job_run(db, tenant_id, "reminder", success=False, detail="unexpected task failure")
            except Exception:  # noqa: BLE001 - even recording the failure must not crash the loop
                logger.exception("Failed to record reminder failure for tenant %s", tenant_id)
