import logging

from app.celery_app import celery_app
from app.services.backup_service import BackupError, run_backup

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.backup_tasks.run_scheduled_backup")
def run_scheduled_backup() -> None:
    """Celery beat entrypoint (PRD §7 / roadmap Phase 6). Full-database
    pg_dump, daily, with retention — see backup_service.py and
    OPERATIONS.md for the manual single-tenant export procedure."""
    try:
        run_backup()
    except BackupError:
        logger.exception("Scheduled backup failed")
