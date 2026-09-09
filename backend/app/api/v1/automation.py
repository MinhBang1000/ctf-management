from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.adapters.base import AdapterError
from app.core.deps import get_db, require_roles
from app.models.job_run_log import JobRunLog
from app.models.member import Member, MemberRole
from app.models.platform import Platform
from app.models.sync_log import SyncLog
from app.models.tenant import Tenant
from app.schemas.automation import JobRunOut, RetryJobRequest, SyncRunOut
from app.services.alerting_service import record_job_run
from app.services.audit_service import record_audit
from app.services.automation_settings_service import get_or_create_automation_settings
from app.services.reminder_service import send_reminders_for_tenant
from app.services.report_service import generate_weekly_report_for_tenant
from app.services.sync_service import SyncCooldownError, run_sync_for_platform

router = APIRouter(prefix="/automation", tags=["automation"])

RETRYABLE_JOB_TYPES = {"sync", "reminder", "weekly_report"}


@router.get("/sync-runs", response_model=list[SyncRunOut])
def list_sync_runs(
    db: Session = Depends(get_db), current: Member = Depends(require_roles(MemberRole.LAB_LEADER))
):
    """§8 — sync run history: time, platform, status, members checked,
    updated Progress count, manual-override conflicts, and errors."""
    rows = (
        db.query(SyncLog, Platform.name)
        .join(Platform, Platform.id == SyncLog.platform_id)
        .filter(SyncLog.tenant_id == current.tenant_id)
        .order_by(SyncLog.run_at.desc())
        .limit(100)
        .all()
    )
    return [
        SyncRunOut(
            id=log.id,
            platform_id=log.platform_id,
            platform_name=platform_name,
            run_at=log.run_at,
            status=log.status,
            members_checked=log.members_checked,
            updated_count=log.updated_count,
            conflicts_count=log.conflicts_count,
            errors=log.errors,
        )
        for log, platform_name in rows
    ]


@router.get("/job-runs", response_model=list[JobRunOut])
def list_job_runs(db: Session = Depends(get_db), current: Member = Depends(require_roles(MemberRole.LAB_LEADER))):
    """§8 — reminder + weekly-report run history for this Lab."""
    return (
        db.query(JobRunLog)
        .filter(JobRunLog.tenant_id == current.tenant_id)
        .order_by(JobRunLog.run_at.desc())
        .limit(100)
        .all()
    )


@router.post("/retry")
def retry_job(
    payload: RetryJobRequest,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    """§8 — "a safe retry action for retryable jobs" that can't bypass
    rate limits or duplicate work: every job type here reuses the exact
    same function the scheduled/manual path already uses, so whatever
    safety net that path has (sync's per-Lab cooldown against the shared
    rate limiter, weekly report's §9 idempotency, reminders' per-
    milestone ReminderLog dedup) applies identically to a retry — there's
    no separate "retry" code path that could skip them.
    """
    if payload.job_type not in RETRYABLE_JOB_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown job_type {payload.job_type!r}")

    tenant = db.get(Tenant, current.tenant_id)

    if payload.job_type == "sync":
        platform = (
            db.query(Platform)
            .filter(Platform.tenant_id == current.tenant_id, Platform.is_focus.is_(True), Platform.is_active.is_(True))
            .first()
        )
        if not platform:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active focus platform configured")
        try:
            result = run_sync_for_platform(db, current.tenant_id, platform)
        except SyncCooldownError as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Sync ran recently for this Lab — try again in {exc.retry_after_seconds}s",
            ) from exc
        except AdapterError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
        summary = f"Retried sync — {result['members_checked']} checked, {len(result['updated'])} updated"
    elif payload.job_type == "reminder":
        # Respect the Lab's own reminder_auto_send preference here too —
        # a manual retry must not bypass the review-queue mode the Lab
        # Leader explicitly chose.
        automation_settings = get_or_create_automation_settings(db, current.tenant_id)
        result = send_reminders_for_tenant(db, tenant, automation_settings)
        record_job_run(db, current.tenant_id, "reminder", success=not result["errors"])
        summary = f"Retried reminders — {len(result['sent'])} sent, {len(result['queued'])} queued for review, {len(result['errors'])} error(s)"
    else:  # weekly_report
        report = generate_weekly_report_for_tenant(db, tenant)
        record_job_run(db, current.tenant_id, "weekly_report", success=report is not None)
        summary = "Retried weekly report generation" + (" — no Semester yet" if report is None else "")

    record_audit(
        db,
        tenant_id=current.tenant_id,
        actor=current,
        action="automation.retried",
        summary=summary,
        target_type="job",
        target_id=None,
    )
    db.commit()
    return {"ok": True, "detail": summary}
