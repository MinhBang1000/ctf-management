import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_super_admin, get_db
from app.db.session import bind_super_admin_context
from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogOut

router = APIRouter(prefix="/admin/audit-log", tags=["admin-audit-log"], dependencies=[Depends(get_current_super_admin)])


@router.get("", response_model=list[AuditLogOut])
def list_all_audit_log(
    tenant_id: uuid.UUID | None = None,
    action: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """§19 — Super Admin's system-wide view, e.g. to review every
    lab.deleted / lab.restored entry (which survive their own Tenant's
    deletion, by design — see audit_logs' own docstring)."""
    bind_super_admin_context(db)
    q = db.query(AuditLog)
    if tenant_id:
        q = q.filter(AuditLog.tenant_id == tenant_id)
    if action:
        q = q.filter(AuditLog.action == action)
    return q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
