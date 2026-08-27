from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_super_admin, get_db
from app.core.security import hash_password
from app.db.session import bind_email_lookup_context
from app.models.member import Member, MemberRole
from app.models.platform import Platform
from app.models.super_admin import SuperAdmin
from app.models.tenant import Tenant
from app.models.sync_log import SyncLog
from app.schemas.dashboard import LabAttentionItem, SuperAdminDashboardOut
from app.schemas.tenant import TenantCreate, TenantOut, TenantUpdate

router = APIRouter(prefix="/admin/labs", tags=["admin-labs"], dependencies=[Depends(get_current_super_admin)])


@router.get("", response_model=list[TenantOut])
def list_labs(db: Session = Depends(get_db)):
    return db.query(Tenant).order_by(Tenant.created_at.desc()).all()


@router.post("", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
def create_lab(payload: TenantCreate, db: Session = Depends(get_db)):
    if db.query(Tenant).filter(Tenant.slug == payload.slug).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already in use")

    # Phase 6 RLS: Members has NO Super-Admin SELECT bypass at all (only a
    # narrow INSERT-only one, just below, for provisioning) — matching the
    # confirmed "no impersonation" design (PRD §9 item 6). This global
    # email-uniqueness check is the same category of system-level lookup
    # as login's, so it reuses that same narrow bypass rather than
    # broadening Super Admin's general read access to Members.
    bind_email_lookup_context(db)
    if db.query(Member).filter(Member.email == payload.lab_leader_email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

    tenant = Tenant(name=payload.name, slug=payload.slug)
    db.add(tenant)
    db.flush()

    lab_leader = Member(
        tenant_id=tenant.id,
        full_name=payload.lab_leader_full_name,
        email=payload.lab_leader_email,
        password_hash=hash_password(payload.lab_leader_password),
        role=MemberRole.LAB_LEADER,
    )
    db.add(lab_leader)

    # Seed a default Root Me platform so Challenge CRUD (Phase 1) has a
    # platform_id to attach to. Full Platform Management UI (adding more
    # platforms, switching focus) is out of scope until Phase 2 per the
    # roadmap (§8) — this is just enough to unblock Phase 1 Challenge CRUD.
    db.add(
        Platform(
            tenant_id=tenant.id,
            name="Root Me",
            adapter_type="rootme",
            base_url="https://api.www.root-me.org",
            is_focus=True,
            is_active=True,
        )
    )

    db.commit()
    db.refresh(tenant)
    return tenant


@router.patch("/{lab_id}", response_model=TenantOut)
def update_lab(lab_id: str, payload: TenantUpdate, db: Session = Depends(get_db)):
    tenant = db.get(Tenant, lab_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found")
    tenant.is_active = payload.is_active
    db.commit()
    db.refresh(tenant)
    return tenant


@router.get("/dashboard", response_model=SuperAdminDashboardOut)
def dashboard(db: Session = Depends(get_db)):
    total = db.query(Tenant).count()
    active_tenants = db.query(Tenant).filter(Tenant.is_active.is_(True)).all()
    active = len(active_tenants)

    # Phase 3 requirement 7: surface which Labs need attention, rather
    # than automation silently failing for them (§6.12 — Super Admin
    # dashboard shows Labs with stuck/failing automation, for support).
    attention: list[LabAttentionItem] = []
    for tenant in active_tenants:
        focus_platform = (
            db.query(Platform)
            .filter(Platform.tenant_id == tenant.id, Platform.is_focus.is_(True), Platform.is_active.is_(True))
            .first()
        )
        if not focus_platform or not focus_platform.has_credentials:
            attention.append(LabAttentionItem(id=tenant.id, name=tenant.name, reason="not_configured"))
            continue

        last_sync = (
            db.query(SyncLog)
            .filter(SyncLog.tenant_id == tenant.id, SyncLog.platform_id == focus_platform.id)
            .order_by(SyncLog.run_at.desc())
            .first()
        )
        if last_sync and last_sync.status == "partial_error":
            attention.append(LabAttentionItem(id=tenant.id, name=tenant.name, reason="sync_errors"))

    return SuperAdminDashboardOut(
        total_labs=total,
        active_labs=active,
        inactive_labs=total - active,
        labs_needing_attention=attention,
    )
