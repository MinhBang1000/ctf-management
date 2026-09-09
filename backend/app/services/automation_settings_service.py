import uuid

from sqlalchemy.orm import Session

from app.models.automation_settings import TenantAutomationSettings


def get_or_create_automation_settings(db: Session, tenant_id: uuid.UUID) -> TenantAutomationSettings:
    """Lazily creates a default-schedule row the first time anyone (the
    Settings API, or the dispatcher task) touches a Tenant's automation
    settings — lets a Lab created before this feature existed pick up
    sane defaults instead of needing a backfill migration for every
    existing Tenant.
    """
    settings = db.query(TenantAutomationSettings).filter(TenantAutomationSettings.tenant_id == tenant_id).first()
    if settings:
        return settings
    settings = TenantAutomationSettings(tenant_id=tenant_id)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings
