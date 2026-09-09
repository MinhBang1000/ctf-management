import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_member, get_db, require_roles
from app.models.challenge import Challenge
from app.models.member import Member, MemberRole
from app.models.platform import Platform
from app.models.semester import Semester
from app.schemas.challenge import ChallengeCreate, ChallengeOut, ChallengeUpdate
from app.services.audit_service import record_audit

router = APIRouter(prefix="/challenges", tags=["challenges"])


def _query(db: Session, tenant_id: uuid.UUID):
    return db.query(Challenge).filter(Challenge.tenant_id == tenant_id)


def _assert_in_tenant(db: Session, tenant_id: uuid.UUID, semester_id: uuid.UUID, platform_id: uuid.UUID, presenter_id: uuid.UUID | None):
    if not db.query(Semester).filter(Semester.id == semester_id, Semester.tenant_id == tenant_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Semester not found in this Lab")
    if not db.query(Platform).filter(Platform.id == platform_id, Platform.tenant_id == tenant_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Platform not found in this Lab")
    if presenter_id is not None and not db.query(Member).filter(
        Member.id == presenter_id, Member.tenant_id == tenant_id
    ).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Presenter not found in this Lab")


@router.get("", response_model=list[ChallengeOut])
def list_challenges(
    semester_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current: Member = Depends(get_current_member),
):
    q = _query(db, current.tenant_id)
    if semester_id:
        q = q.filter(Challenge.semester_id == semester_id)
    return q.order_by(Challenge.week_number.asc(), Challenge.deadline_at.asc()).all()


@router.post("", response_model=ChallengeOut, status_code=status.HTTP_201_CREATED)
def create_challenge(
    payload: ChallengeCreate,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    _assert_in_tenant(db, current.tenant_id, payload.semester_id, payload.platform_id, payload.presenter_id)
    challenge = Challenge(tenant_id=current.tenant_id, **payload.model_dump())
    db.add(challenge)
    db.flush()
    record_audit(
        db,
        tenant_id=current.tenant_id,
        actor=current,
        action="challenge.created",
        summary=f"Created challenge {payload.title!r} (week {payload.week_number})",
        target_type="challenge",
        target_id=challenge.id,
    )
    db.commit()
    db.refresh(challenge)
    return challenge


@router.patch("/{challenge_id}", response_model=ChallengeOut)
def update_challenge(
    challenge_id: uuid.UUID,
    payload: ChallengeUpdate,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    challenge = _query(db, current.tenant_id).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found")

    data = payload.model_dump(exclude_unset=True)
    _assert_in_tenant(
        db,
        current.tenant_id,
        data.get("semester_id", challenge.semester_id),
        data.get("platform_id", challenge.platform_id),
        data.get("presenter_id", challenge.presenter_id),
    )

    changes = []
    rootme_association_changed = False
    for key, value in data.items():
        old_value = getattr(challenge, key)
        if old_value == value:
            continue
        changes.append(f"{key}: {old_value!r} -> {value!r}")
        if key == "external_challenge_id":
            rootme_association_changed = True
        setattr(challenge, key, value)

    if changes:
        summary = f"Updated challenge {challenge.title!r}: " + "; ".join(changes)
        if rootme_association_changed:
            summary += " (Root Me association changed — future sync will match against the new ID)"
        record_audit(
            db,
            tenant_id=current.tenant_id,
            actor=current,
            action="challenge.updated",
            summary=summary,
            target_type="challenge",
            target_id=challenge.id,
        )
    db.commit()
    db.refresh(challenge)
    return challenge


@router.delete("/{challenge_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_challenge(
    challenge_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    challenge = _query(db, current.tenant_id).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found")
    record_audit(
        db,
        tenant_id=current.tenant_id,
        actor=current,
        action="challenge.deleted",
        summary=f"Deleted challenge {challenge.title!r} (week {challenge.week_number})",
        target_type="challenge",
        target_id=challenge.id,
    )
    db.delete(challenge)
    db.commit()
