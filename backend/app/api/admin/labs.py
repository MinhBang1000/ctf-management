import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_super_admin, get_db
from app.core.security import hash_password
from app.db.session import bind_email_lookup_context, enable_email_lookup_now, enable_tenant_context_now
from app.models.challenge import Challenge
from app.models.member import Member, MemberRole
from app.models.platform import Platform
from app.models.progress import Progress
from app.models.report import Report
from app.models.semester import Semester
from app.models.super_admin import SuperAdmin
from app.models.tenant import Tenant
from app.models.sync_log import SyncLog
from app.models.tenant_data_job import TenantDataJob
from app.schemas.dashboard import LabAttentionItem, SuperAdminDashboardOut
from app.schemas.member import MemberOut
from app.schemas.tenant import (
    AssignLeaderRequest,
    DeleteLabRequest,
    DeletionPreview,
    RestoreBundleRequest,
    RestoreResult,
    TenantCreate,
    TenantDataJobOut,
    TenantOut,
    TenantUpdate,
)
from app.services.audit_service import record_audit
from app.services.tenant_data_service import RestoreError, export_tenant_bundle, restore_tenant_bundle

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
def update_lab(
    lab_id: str,
    payload: TenantUpdate,
    db: Session = Depends(get_db),
    current: SuperAdmin = Depends(get_current_super_admin),
):
    tenant = db.get(Tenant, lab_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found")
    tenant.is_active = payload.is_active
    record_audit(
        db, tenant_id=tenant.id, actor=current,
        action="lab.suspended" if not payload.is_active else "lab.reactivated",
        summary=f"{'Suspended' if not payload.is_active else 'Reactivated'} Lab {tenant.name}",
        target_type="tenant", target_id=tenant.id,
    )
    db.commit()
    db.refresh(tenant)
    return tenant


@router.post("/{lab_id}/assign-leader", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def assign_leader(
    lab_id: uuid.UUID,
    payload: AssignLeaderRequest,
    db: Session = Depends(get_db),
    current: SuperAdmin = Depends(get_current_super_admin),
):
    """§15 (decided) — when a Lab has no active Lab Leader left, the Super
    Admin adds one directly from the Console. Deliberately narrow: it only
    creates a brand-new account (no reading/browsing this Lab's existing
    Members — see AssignLeaderRequest's docstring), and it refuses to run
    at all if the Lab already has an active Lab Leader, so it can never be
    used as a side-channel to just add extra leaders at will.
    """
    tenant = db.get(Tenant, lab_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found")

    enable_tenant_context_now(db, lab_id)
    active_leaders = (
        db.query(Member)
        .filter(Member.tenant_id == lab_id, Member.role == MemberRole.LAB_LEADER, Member.active.is_(True))
        .count()
    )
    if active_leaders > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This Lab already has an active Lab Leader — use that Lab Leader's own ownership transfer instead.",
        )

    enable_email_lookup_now(db)
    if db.query(Member).filter(Member.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

    enable_tenant_context_now(db, lab_id)
    leader = Member(
        tenant_id=lab_id,
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=MemberRole.LAB_LEADER,
    )
    db.add(leader)
    db.flush()
    record_audit(
        db, tenant_id=lab_id, actor=current, action="lab.leader_assigned_by_admin",
        summary=f"Super Admin assigned {payload.email} as Lab Leader (no active Lab Leader remained)",
        target_type="member", target_id=leader.id,
    )
    db.commit()
    db.refresh(leader)
    return leader


@router.get("/{lab_id}/deletion-preview", response_model=DeletionPreview)
def deletion_preview(
    lab_id: uuid.UUID, db: Session = Depends(get_db), current: SuperAdmin = Depends(get_current_super_admin)
):
    """§16 — "Show the affected data before deletion.\" """
    tenant = db.get(Tenant, lab_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found")
    enable_tenant_context_now(db, lab_id)
    return DeletionPreview(
        tenant_name=tenant.name,
        member_count=db.query(Member).filter(Member.tenant_id == lab_id).count(),
        semester_count=db.query(Semester).filter(Semester.tenant_id == lab_id).count(),
        challenge_count=db.query(Challenge).filter(Challenge.tenant_id == lab_id).count(),
        progress_count=(
            db.query(Progress).join(Challenge, Progress.challenge_id == Challenge.id)
            .filter(Challenge.tenant_id == lab_id).count()
        ),
        report_count=db.query(Report).filter(Report.tenant_id == lab_id).count(),
        platform_count=db.query(Platform).filter(Platform.tenant_id == lab_id).count(),
    )


@router.delete("/{lab_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lab(
    lab_id: uuid.UUID,
    payload: DeleteLabRequest,
    db: Session = Depends(get_db),
    current: SuperAdmin = Depends(get_current_super_admin),
):
    """§16 — immediate, not soft/recoverable (decided) — but only after an
    explicit confirmation that names the Lab, checked here, not just in
    the frontend. Cascade relies on the DB's own ON DELETE CASCADE FKs +
    the retroactive super-admin DELETE-bypass RLS policies (see the
    required_features_schema migration's docstring) — audit_logs and
    tenant_data_jobs deliberately don't cascade, so this Lab's history
    survives its own deletion.
    """
    from sqlalchemy import text

    tenant = db.get(Tenant, lab_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found")
    if payload.confirm_name != tenant.name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm_name must exactly match the Lab's current name",
        )
    tenant_name = tenant.name
    record_audit(
        db, tenant_id=lab_id, actor=current, action="lab.deleted",
        summary=f"Deleted Lab {tenant_name!r} (id {lab_id})", target_type="tenant", target_id=lab_id,
    )
    db.commit()
    db.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": str(lab_id)})
    db.commit()


@router.get("/{lab_id}/export")
def export_lab(
    lab_id: uuid.UUID, db: Session = Depends(get_db), current: SuperAdmin = Depends(get_current_super_admin)
):
    """§17 — Super Admin export of any Lab (the Lab-Leader self-service
    version is GET /api/v1/export)."""
    tenant = db.get(Tenant, lab_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found")
    enable_tenant_context_now(db, lab_id)
    bundle = export_tenant_bundle(db, tenant)
    db.add(
        TenantDataJob(
            tenant_id=lab_id, job_type="export", status="done",
            requested_by_email=current.email, format_version=bundle["format_version"],
            downloaded_at=datetime.now(timezone.utc),
        )
    )
    record_audit(
        db, tenant_id=lab_id, actor=current, action="lab.exported",
        summary=f"Super Admin exported Lab {tenant.name}", target_type="tenant", target_id=lab_id,
    )
    db.commit()
    filename = f"{tenant.slug}-export-{bundle['exported_at'][:10]}.json"
    return Response(
        content=json.dumps(bundle, indent=2), media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{lab_id}/backup", response_model=TenantDataJobOut, status_code=status.HTTP_201_CREATED)
def backup_lab(
    lab_id: uuid.UUID, db: Session = Depends(get_db), current: SuperAdmin = Depends(get_current_super_admin)
):
    """§18 — unlike export, this is saved to disk (under BACKUP_DIR/tenants/)
    so it can be listed and restored later without the Super Admin having
    kept the downloaded file themselves."""
    tenant = db.get(Tenant, lab_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found")
    enable_tenant_context_now(db, lab_id)
    bundle = export_tenant_bundle(db, tenant)

    backup_dir = Path(settings.BACKUP_DIR) / "tenants" / str(lab_id)
    backup_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{bundle['exported_at'].replace(':', '-')}.json"
    file_path = backup_dir / filename
    file_path.write_text(json.dumps(bundle, indent=2))
    os.chmod(file_path, 0o600)

    job = TenantDataJob(
        tenant_id=lab_id, job_type="backup", status="done", requested_by_email=current.email,
        format_version=bundle["format_version"], file_path=str(file_path), completed_at=datetime.now(timezone.utc),
    )
    db.add(job)
    record_audit(
        db, tenant_id=lab_id, actor=current, action="lab.backed_up",
        summary=f"Backed up Lab {tenant.name} to {file_path}", target_type="tenant", target_id=lab_id,
    )
    db.commit()
    db.refresh(job)
    return job


@router.get("/{lab_id}/backups", response_model=list[TenantDataJobOut])
def list_lab_backups(
    lab_id: uuid.UUID, db: Session = Depends(get_db), current: SuperAdmin = Depends(get_current_super_admin)
):
    enable_tenant_context_now(db, lab_id)
    return (
        db.query(TenantDataJob)
        .filter(TenantDataJob.tenant_id == lab_id, TenantDataJob.job_type == "backup")
        .order_by(TenantDataJob.created_at.desc())
        .all()
    )


@router.get("/backups/{job_id}/download")
def download_lab_backup(
    job_id: uuid.UUID, db: Session = Depends(get_db), current: SuperAdmin = Depends(get_current_super_admin)
):
    from app.db.session import bind_super_admin_context

    bind_super_admin_context(db)
    job = db.get(TenantDataJob, job_id)
    if not job or job.job_type != "backup" or not job.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup not found")
    path = Path(job.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup file no longer exists on disk")
    job.downloaded_at = datetime.now(timezone.utc)
    db.commit()
    return Response(
        content=path.read_text(), media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


@router.post("/restore", response_model=RestoreResult)
def restore_lab(
    payload: RestoreBundleRequest, db: Session = Depends(get_db), current: SuperAdmin = Depends(get_current_super_admin)
):
    """§18 — restore from a previously exported/backed-up bundle. See
    restore_tenant_bundle's own docstring for exactly how ID/email
    conflicts are handled."""
    try:
        new_tenant_id, warnings = restore_tenant_bundle(db, payload.bundle, payload.mode, payload.target_tenant_id)
    except RestoreError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    record_audit(
        db, tenant_id=new_tenant_id, actor=current, action="lab.restored",
        summary=f"Restored Lab data (mode={payload.mode}) into tenant {new_tenant_id}"
        + (f" — warnings: {'; '.join(warnings)}" if warnings else ""),
        target_type="tenant", target_id=new_tenant_id,
    )
    db.commit()
    return RestoreResult(tenant_id=new_tenant_id, warnings=warnings)


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
