import json

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_member, get_db, require_roles
from app.models.member import Member, MemberRole
from app.models.tenant import Tenant
from app.models.tenant_data_job import TenantDataJob
from app.services.audit_service import record_audit
from app.services.tenant_data_service import export_tenant_bundle

router = APIRouter(prefix="/export", tags=["data-export"])


@router.get("")
def export_own_lab(
    db: Session = Depends(get_db), current: Member = Depends(require_roles(MemberRole.LAB_LEADER))
):
    """§17 — a Lab Leader's self-service export of their own Lab. Streamed
    directly, never kept server-side (see TenantDataJob's file_path
    docstring)."""
    tenant = db.get(Tenant, current.tenant_id)
    bundle = export_tenant_bundle(db, tenant)
    db.add(
        TenantDataJob(
            tenant_id=current.tenant_id, job_type="export", status="done",
            requested_by_email=current.email, format_version=bundle["format_version"],
        )
    )
    record_audit(
        db, tenant_id=current.tenant_id, actor=current, action="lab.exported",
        summary=f"{current.email} exported this Lab's data", target_type="tenant", target_id=current.tenant_id,
    )
    db.commit()
    filename = f"{tenant.slug}-export-{bundle['exported_at'][:10]}.json"
    return Response(
        content=json.dumps(bundle, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
