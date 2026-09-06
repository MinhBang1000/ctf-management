from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.models.audit_log import AuditLog
from app.models.member import Member, MemberRole
from app.schemas.audit_log import AuditLogOut

router = APIRouter(prefix="/audit-log", tags=["audit-log"])


@router.get("", response_model=list[AuditLogOut])
def list_audit_log(
    action: str | None = None,
    target_type: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    """§19 — "a filtered, paginated audit-log viewer for authorized
    roles." Lab Leader sees only their own Lab's entries (RLS also
    enforces this independently — see audit_logs_tenant_all)."""
    q = db.query(AuditLog).filter(AuditLog.tenant_id == current.tenant_id)
    if action:
        q = q.filter(AuditLog.action == action)
    if target_type:
        q = q.filter(AuditLog.target_type == target_type)
    return q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
