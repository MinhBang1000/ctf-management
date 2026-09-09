import logging

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.system_job_run_log import SystemJobRunLog
from app.services.backup_service import BackupError, run_backup

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.backup_tasks.run_scheduled_backup")
def run_scheduled_backup() -> None:
    """Celery beat entrypoint (PRD §7 / roadmap Phase 6). Full-database
    pg_dump, daily, with retention — see backup_service.py and
    OPERATIONS.md for the manual single-tenant export procedure.

    §8 — records a SystemJobRunLog row either way, since this job has no
    single Tenant to scope a JobRunLog to (see that model's docstring)."""
    db = SessionLocal()
    try:
        from app.db.session import bind_super_admin_context

        bind_super_admin_context(db)
        try:
            run_backup()
        except BackupError as exc:
            logger.exception("Scheduled backup failed")
            db.add(SystemJobRunLog(job_type="backup", status="error", detail=str(exc)))
        else:
            db.add(SystemJobRunLog(job_type="backup", status="ok"))
        db.commit()
    finally:
        db.close()
