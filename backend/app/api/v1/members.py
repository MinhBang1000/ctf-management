import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_member, get_db, require_roles
from app.core.security import hash_password
from app.models.member import Member, MemberRole
from app.models.member_platform_account import MemberPlatformAccount
from app.models.platform import Platform
from app.schemas.member import MemberCreate, MemberOut, MemberUpdate, PlatformAccountIn, PlatformAccountOut

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

    if payload.full_name is not None:
        member.full_name = payload.full_name
    if payload.role is not None:
        member.role = payload.role
    if payload.active is not None:
        member.active = payload.active

    db.commit()
    db.refresh(member)
    return member


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member(
    member_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    member = _member_query(db, current.tenant_id).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
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
    db.commit()
    return db.query(MemberPlatformAccount).filter(MemberPlatformAccount.member_id == member_id).all()
