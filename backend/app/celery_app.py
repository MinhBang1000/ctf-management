from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery("hslab", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "sync-all-tenants": {
            "task": "app.tasks.sync_tasks.sync_all_tenants",
            # Config value, not hardcoded (PRD §4.2.1 step 2) — see
            # SYNC_INTERVAL_MINUTES in .env. Root Me gives exact
            # completion timestamps, so frequency only affects detection
            # speed, not accuracy.
            "schedule": settings.SYNC_INTERVAL_MINUTES * 60,
        },
        "check-reminders": {
            "task": "app.tasks.reminder_tasks.check_reminders",
            "schedule": crontab(hour=settings.REMINDER_CHECK_HOUR_UTC, minute=0),
        },
        "generate-weekly-reports": {
            "task": "app.tasks.report_tasks.generate_weekly_reports",
            "schedule": crontab(
                hour=settings.WEEKLY_REPORT_HOUR_UTC,
                minute=0,
                day_of_week=settings.WEEKLY_REPORT_DAY_OF_WEEK,
            ),
        },
        "run-scheduled-backup": {
            "task": "app.tasks.backup_tasks.run_scheduled_backup",
            "schedule": crontab(hour=settings.BACKUP_HOUR_UTC, minute=0),
        },
    },
)

# Explicit imports rather than autodiscover_tasks(["app.tasks"]): Celery's
# autodiscovery only looks for a module literally named tasks.py per
# package, which doesn't match app/tasks/sync_tasks.py etc.
import app.tasks.sync_tasks  # noqa: E402,F401
import app.tasks.reminder_tasks  # noqa: E402,F401
import app.tasks.report_tasks  # noqa: E402,F401
import app.tasks.backup_tasks  # noqa: E402,F401
