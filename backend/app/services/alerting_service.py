import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.job_run_log import JobRunLog
from app.models.super_admin import SuperAdmin
from app.models.sync_log import SyncLog
from app.models.tenant import Tenant
from app.services.email_service import EmailConfigError, EmailSendError, send_system_email

logger = logging.getLogger(__name__)

JOB_LABELS = {"sync": "sync", "reminder": "reminder", "weekly_report": "weekly report"}


def record_job_run(db: Session, tenant_id: uuid.UUID, job_type: str, success: bool, detail: str | None = None) -> None:
    """For reminder/weekly_report jobs, which — unlike sync — had no
    persisted per-run history before Phase 6 (only a Python logger call).
    Writes the run, then checks whether this tenant+job_type just crossed
    the alert threshold."""
    db.add(JobRunLog(tenant_id=tenant_id, job_type=job_type, status="ok" if success else "error", detail=detail))
    db.commit()
    check_and_alert(db, tenant_id, job_type)


def check_and_alert(db: Session, tenant_id: uuid.UUID, job_type: str) -> None:
    """Fires exactly once per failure streak: checked with ==, not >=, so
    a Tenant stuck at N+ consecutive failures doesn't re-alert Super Admin
    on every subsequent run once already flagged.

    Fetches threshold+1 rows, not just threshold — with a hard limit of
    exactly `threshold`, the count can never exceed threshold, so on every
    run *after* the alert-worthy one it would still read as == threshold
    and re-fire every single time (caught by a real test, not a hunch).
    The extra row lets "exactly threshold" and "more than threshold" read
    as different numbers, so the count is capped-but-distinguishable
    instead of permanently stuck.
    """
    threshold = settings.ALERT_FAILURE_THRESHOLD
    fetch_limit = threshold + 1
    if job_type == "sync":
        count = _trailing_failures(
            db.query(SyncLog.status).filter(SyncLog.tenant_id == tenant_id).order_by(SyncLog.run_at.desc()),
            failure_value="partial_error",
            limit=fetch_limit,
        )
    else:
        count = _trailing_failures(
            db.query(JobRunLog.status)
            .filter(JobRunLog.tenant_id == tenant_id, JobRunLog.job_type == job_type)
            .order_by(JobRunLog.run_at.desc()),
            failure_value="error",
            limit=fetch_limit,
        )

    if count == threshold:
        _send_alert(db, tenant_id, job_type, count)


def _trailing_failures(query, failure_value: str, limit: int) -> int:
    count = 0
    for (status_value,) in query.limit(limit).all():
        if status_value != failure_value:
            break
        count += 1
    return count


def _send_alert(db: Session, tenant_id: uuid.UUID, job_type: str, count: int) -> None:
    tenant = db.get(Tenant, tenant_id)
    tenant_name = tenant.name if tenant else str(tenant_id)
    label = JOB_LABELS.get(job_type, job_type)

    subject = f"[HSLab CTF Classroom] {label} failing repeatedly for {tenant_name}"
    body = (
        f'The {label} job has failed {count} times in a row for Lab "{tenant_name}".\n\n'
        "This usually means credentials or configuration need attention (e.g. an expired "
        "Root Me key, or broken SMTP). Check that Lab's Platform/Settings, or the Super "
        "Admin console's Labs needing attention list for more context.\n\n"
        "— HSLab CTF Classroom automated alert"
    )

    admins = db.query(SuperAdmin).filter(SuperAdmin.active.is_(True)).all()
    if not admins:
        logger.warning("Alert threshold hit for tenant %s (%s) but no active Super Admin to notify", tenant_id, job_type)
        return

    for admin in admins:
        try:
            send_system_email(admin.email, subject, body)
        except (EmailConfigError, EmailSendError):
            logger.exception("Failed to send alert email to super admin %s", admin.email)
