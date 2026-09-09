import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_member, get_db, require_roles
from app.core.security import hash_password
from app.db.session import enable_email_lookup_now
from app.models.member import Member, MemberRole
from app.models.member_platform_account import MemberPlatformAccount
from app.models.platform import Platform
from app.schemas.member import (
    MemberCreate,
    MemberOut,
    MemberResetPasswordRequest,
    MemberUpdate,
    PlatformAccountIn,
    PlatformAccountOut,
    TransferOwnershipRequest,
)
from app.services.audit_service import record_audit
from app.services.member_service import LastLabLeaderError, assert_not_last_lab_leader

router = APIRouter(prefix="/members", tags=["members"])


def _member_query(db: Session, tenant_id: uuid.UUID):
    return db.query(Member).options(joinedload(Member.platform_accounts)).filter(Member.tenant_id == tenant_id)


@router.get("", response_model=list[MemberOut])
def list_members(db: Session = Depends(get_db), current: Member = Depends(get_current_member)):
    return _member_query(db, current.tenant_id).order_by(Member.joined_at.desc()).all()


@router.get("/{member_id}", response_model=MemberOut)
def get_member(member_id: uuid.UUID, db: Session = Depends(get_db), current: Member = Depends(get_current_member)):
    member = _member_query(db, current.tenant_id).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    return member


def _validate_platform_accounts(db: Session, tenant_id: uuid.UUID, accounts: list[PlatformAccountIn]):
    for acc in accounts:
        platform = (
            db.query(Platform)
            .filter(Platform.id == acc.platform_id, Platform.tenant_id == tenant_id)
            .first()
        )
        if not platform:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Platform {acc.platform_id} not found in this Lab",
            )


@router.post("", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def create_member(
    payload: MemberCreate,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    if db.query(Member).filter(Member.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
    _validate_platform_accounts(db, current.tenant_id, payload.platform_accounts)

    member = Member(
        tenant_id=current.tenant_id,
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(member)
    db.flush()

    for acc in payload.platform_accounts:
        db.add(
            MemberPlatformAccount(
                member_id=member.id,
                platform_id=acc.platform_id,
                external_username=acc.external_username,
                external_user_id=acc.external_user_id,
            )
        )

    record_audit(
        db,
        tenant_id=current.tenant_id,
        actor=current,
        action="member.created",
        summary=f"Created member {payload.full_name} <{payload.email}> as {payload.role.value}",
        target_type="member",
        target_id=member.id,
    )
    db.commit()
    db.refresh(member)
    return _member_query(db, current.tenant_id).filter(Member.id == member.id).first()


@router.patch("/{member_id}", response_model=MemberOut)
def update_member(
    member_id: uuid.UUID,
    payload: MemberUpdate,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    member = _member_query(db, current.tenant_id).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    # §14 — check BEFORE applying any change, using the state the row is
    # in right now (would this change take away its last active Leader?).
    would_deactivate = payload.active is False
    would_demote = payload.role is not None and payload.role != MemberRole.LAB_LEADER
    if would_deactivate or would_demote:
        try:
            assert_not_last_lab_leader(db, member)
        except LastLabLeaderError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    changes = []
    if payload.full_name is not None and payload.full_name != member.full_name:
        changes.append(f"full_name: {member.full_name!r} -> {payload.full_name!r}")
        member.full_name = payload.full_name
    if payload.email is not None and payload.email != member.email:
        # §3 — "Handle duplicate email addresses with a clear conflict
        # response": email is unique system-wide (see Member model), and
        # RLS hides other tenants' rows from a plain tenant-scoped query,
        # so this check needs the same cross-tenant lookup bypass login
        # and create_lab already use — otherwise it'd silently miss a
        # cross-Lab duplicate and let the DB's own constraint raise an
        # uncaught 500 on commit instead of a clean 409 here.
        enable_email_lookup_now(db)
        if db.query(Member).filter(Member.email == payload.email, Member.id != member.id).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
        changes.append(f"email: {member.email!r} -> {payload.email!r}")
        member.email = payload.email
    if payload.role is not None and payload.role != member.role:
        changes.append(f"role: {member.role.value} -> {payload.role.value}")
        member.role = payload.role
    if payload.active is not None and payload.active != member.active:
        changes.append(f"active: {member.active} -> {payload.active}")
        member.active = payload.active

    if changes:
        record_audit(
            db,
            tenant_id=current.tenant_id,
            actor=current,
            action="member.updated",
            summary=f"Updated member {member.email}: " + "; ".join(changes),
            target_type="member",
            target_id=member.id,
        )
    db.commit()
    db.refresh(member)
    return member


@router.post("/{member_id}/reset-password", response_model=MemberOut)
def reset_member_password(
    member_id: uuid.UUID,
    payload: MemberResetPasswordRequest,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    """§2/§3 — Lab Leader sets a new password for a Member in the same
    Lab directly (like create_member's temporary password, communicated
    out of band) rather than a token flow, since the Leader already has
    the authority to act on this account. Invalidates the Member's
    existing sessions immediately, same as any other password change."""
    member = _member_query(db, current.tenant_id).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    member.password_hash = hash_password(payload.new_password)
    member.token_version += 1
    record_audit(
        db,
        tenant_id=current.tenant_id,
        actor=current,
        action="member.password_reset_by_leader",
        summary=f"Lab Leader reset the password for {member.email}",
        target_type="member",
        target_id=member.id,
    )
    db.commit()
    db.refresh(member)
    return member


@router.post("/{member_id}/transfer-ownership", response_model=MemberOut)
def transfer_ownership(
    member_id: uuid.UUID,
    payload: TransferOwnershipRequest,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    """§15 — hand primary Lab Leader responsibility to another active
    Member. Promotes the target first, then (only if requested) demotes
    the initiator — in that order, so assert_not_last_lab_leader always
    sees at least the newly-promoted Leader before it ever has to allow
    stepping the initiator down."""
    if not payload.confirm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ownership transfer requires explicit confirmation")

    target = _member_query(db, current.tenant_id).filter(Member.id == member_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if target.id == current.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot transfer ownership to yourself")
    if not target.active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot transfer ownership to an inactive Member")

    was_already_leader = target.role == MemberRole.LAB_LEADER
    target.role = MemberRole.LAB_LEADER

    if payload.demote_self_to is not None:
        try:
            assert_not_last_lab_leader(db, current)
        except LastLabLeaderError as exc:
            # Unreachable in practice (target is now a Leader too, in this
            # same transaction) unless demote_self_to somehow targeted the
            # very Member being promoted — kept as a hard backstop, not a
            # normal user-facing path.
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        current.role = payload.demote_self_to

    record_audit(
        db,
        tenant_id=current.tenant_id,
        actor=current,
        action="lab.ownership_transferred",
        summary=(
            f"{current.email} transferred Lab Leader ownership to {target.email}"
            + (f" (self demoted to {payload.demote_self_to.value})" if payload.demote_self_to else "")
            + (" (was already a Leader)" if was_already_leader else "")
        ),
        target_type="member",
        target_id=target.id,
    )
    db.commit()
    db.refresh(target)
    return target


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member(
    member_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    member = _member_query(db, current.tenant_id).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    try:
        assert_not_last_lab_leader(db, member)
    except LastLabLeaderError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    record_audit(
        db,
        tenant_id=current.tenant_id,
        actor=current,
        action="member.deleted",
        summary=f"Deleted member {member.email} ({member.role.value})",
        target_type="member",
        target_id=member.id,
    )
    db.delete(member)
    db.commit()


@router.put("/{member_id}/platform-accounts", response_model=list[PlatformAccountOut])
def replace_platform_accounts(
    member_id: uuid.UUID,
    accounts: list[PlatformAccountIn],
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    """Replaces all platform-account links for a Member.

    external_user_id (Root Me id_auteur) is required on every entry per
    PRD §6.3 / the §5 ERD note — enforced by PlatformAccountIn itself.
    """
    member = _member_query(db, current.tenant_id).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    _validate_platform_accounts(db, current.tenant_id, accounts)

    db.query(MemberPlatformAccount).filter(MemberPlatformAccount.member_id == member_id).delete()
    for acc in accounts:
        db.add(
            MemberPlatformAccount(
                member_id=member_id,
                platform_id=acc.platform_id,
                external_username=acc.external_username,
                external_user_id=acc.external_user_id,
            )
        )
    record_audit(
        db,
        tenant_id=current.tenant_id,
        actor=current,
        action="member.platform_accounts_updated",
        summary=f"Updated platform accounts for {member.email} ({len(accounts)} linked)",
        target_type="member",
        target_id=member.id,
    )
    db.commit()
    return db.query(MemberPlatformAccount).filter(MemberPlatformAccount.member_id == member_id).all()
