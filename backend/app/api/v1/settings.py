from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.models.member import Member, MemberRole
from app.models.tenant import Tenant
from app.schemas.platform import TestConnectionResult
from app.schemas.settings import (
    ProfessorEmailUpdate,
    SendTestEmailRequest,
    SMTPConfigOut,
    SMTPConfigUpdate,
    TenantSettingsOut,
)
from app.services.audit_service import record_audit
from app.services.email_service import EmailConfigError, EmailSendError, send_test_email

router = APIRouter(prefix="/settings", tags=["settings"])


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
