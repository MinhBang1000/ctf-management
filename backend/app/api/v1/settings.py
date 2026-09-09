from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.models.member import Member, MemberRole
from app.models.tenant import Tenant
from app.schemas.automation_settings import AutomationSettingsOut, AutomationSettingsUpdate, RepeatScheduleOut
from app.schemas.platform import TestConnectionResult
from app.schemas.settings import (
    ProfessorEmailUpdate,
    SendTestEmailRequest,
    SMTPConfigOut,
    SMTPConfigUpdate,
    TenantSettingsOut,
)
from app.services.audit_service import record_audit
from app.services.automation_settings_service import get_or_create_automation_settings
from app.services.email_service import EmailConfigError, EmailSendError, send_test_email

router = APIRouter(prefix="/settings", tags=["settings"])


def _automation_out(s) -> AutomationSettingsOut:
    return AutomationSettingsOut(
        reminder=RepeatScheduleOut(
            enabled=s.reminder_enabled, repeat=s.reminder_repeat, time_of_day=s.reminder_time_of_day,
            day_of_week=s.reminder_day_of_week, day_of_month=s.reminder_day_of_month,
            interval_days=s.reminder_interval_days, last_fired_at=s.reminder_last_fired_at.isoformat(),
        ),
        weekly_report=RepeatScheduleOut(
            enabled=s.weekly_report_enabled, repeat=s.weekly_report_repeat, time_of_day=s.weekly_report_time_of_day,
            day_of_week=s.weekly_report_day_of_week, day_of_month=s.weekly_report_day_of_month,
            interval_days=s.weekly_report_interval_days, last_fired_at=s.weekly_report_last_fired_at.isoformat(),
        ),
        weekly_report_auto_send=s.weekly_report_auto_send,
    )


def _smtp_out(tenant: Tenant) -> SMTPConfigOut:
    cfg = tenant.smtp_config or {}
    return SMTPConfigOut(
        host=cfg.get("host"),
        port=cfg.get("port"),
        username=cfg.get("username"),
        from_address=cfg.get("from_address"),
        use_tls=cfg.get("use_tls"),
        has_credentials=tenant.has_smtp_credentials,
    )


@router.get("", response_model=TenantSettingsOut)
def get_settings(db: Session = Depends(get_db), current: Member = Depends(require_roles(MemberRole.LAB_LEADER))):
    tenant = db.get(Tenant, current.tenant_id)
    return TenantSettingsOut(smtp=_smtp_out(tenant), professor_email=tenant.professor_email)


@router.patch("/smtp", response_model=SMTPConfigOut)
def update_smtp(
    payload: SMTPConfigUpdate,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    tenant = db.get(Tenant, current.tenant_id)
    tenant.smtp_config = {
        "host": payload.host,
        "port": payload.port,
        "username": payload.username,
        "password": payload.password,
        "from_address": payload.from_address,
        "use_tls": payload.use_tls,
    }
    record_audit(
        db, tenant_id=current.tenant_id, actor=current, action="settings.smtp_updated",
        summary=f"{current.email} updated SMTP settings (host={payload.host!r})", target_type="tenant",
        target_id=current.tenant_id,
    )
    db.commit()
    db.refresh(tenant)
    return _smtp_out(tenant)


@router.patch("/professor-email", response_model=TenantSettingsOut)
def update_professor_email(
    payload: ProfessorEmailUpdate,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    tenant = db.get(Tenant, current.tenant_id)
    tenant.professor_email = payload.professor_email
    record_audit(
        db, tenant_id=current.tenant_id, actor=current, action="settings.professor_email_updated",
        summary=f"{current.email} set professor email to {payload.professor_email!r}", target_type="tenant",
        target_id=current.tenant_id,
    )
    db.commit()
    db.refresh(tenant)
    return TenantSettingsOut(smtp=_smtp_out(tenant), professor_email=tenant.professor_email)


@router.post("/smtp/test-email", response_model=TestConnectionResult)
def test_smtp(
    payload: SendTestEmailRequest,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    tenant = db.get(Tenant, current.tenant_id)
    try:
        send_test_email(tenant, payload.to_address)
    except (EmailConfigError, EmailSendError) as exc:
        return TestConnectionResult(ok=False, detail=str(exc))
    return TestConnectionResult(ok=True, detail=f"Test email sent to {payload.to_address}")


@router.get("/automation", response_model=AutomationSettingsOut)
def get_automation_settings(
    db: Session = Depends(get_db), current: Member = Depends(require_roles(MemberRole.LAB_LEADER))
):
    return _automation_out(get_or_create_automation_settings(db, current.tenant_id))


@router.patch("/automation", response_model=AutomationSettingsOut)
def update_automation_settings(
    payload: AutomationSettingsUpdate,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    """Editing a schedule does NOT touch its *_last_fired_at anchor — only
    the dispatcher does that, after it actually runs the task. Changing
    the schedule mid-cycle just changes when the NEXT fire lands, computed
    from whenever it last fired (or was created), same as any calendar
    app moving a reminder around."""
    s = get_or_create_automation_settings(db, current.tenant_id)
    r, w = payload.reminder, payload.weekly_report
    s.reminder_enabled, s.reminder_repeat, s.reminder_time_of_day = r.enabled, r.repeat, r.time_of_day
    s.reminder_day_of_week, s.reminder_day_of_month, s.reminder_interval_days = r.day_of_week, r.day_of_month, r.interval_days
    s.weekly_report_enabled, s.weekly_report_repeat, s.weekly_report_time_of_day = w.enabled, w.repeat, w.time_of_day
    s.weekly_report_day_of_week, s.weekly_report_day_of_month, s.weekly_report_interval_days = (
        w.day_of_week, w.day_of_month, w.interval_days,
    )
    s.weekly_report_auto_send = payload.weekly_report_auto_send
    record_audit(
        db, tenant_id=current.tenant_id, actor=current, action="settings.automation_updated",
        summary=f"{current.email} updated automation settings (reminder={r.repeat}, weekly_report={w.repeat}, "
        f"auto_send={payload.weekly_report_auto_send})",
        target_type="tenant", target_id=current.tenant_id,
    )
    db.commit()
    db.refresh(s)
    return _automation_out(s)
