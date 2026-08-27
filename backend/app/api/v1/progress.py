import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_member, get_db, require_roles
from app.models.challenge import Challenge
from app.models.member import Member, MemberRole
from app.models.progress import DetectedBy, Progress
from app.schemas.progress import ProgressOut, ProgressUpsert

router = APIRouter(prefix="/progress", tags=["progress"])


def _query(db: Session, tenant_id: uuid.UUID):
    # Progress has no direct tenant_id column (PRD §5 ERD) — scope via the
    # tenant-owned Challenge it belongs to.
    return db.query(Progress).join(Challenge, Progress.challenge_id == Challenge.id).filter(
        Challenge.tenant_id == tenant_id
    )


@router.get("", response_model=list[ProgressOut])
def list_progress(
    challenge_id: uuid.UUID | None = None,
    member_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current: Member = Depends(get_current_member),
):
    q = _query(db, current.tenant_id)
    if challenge_id:
        q = q.filter(Progress.challenge_id == challenge_id)
    if member_id:
        q = q.filter(Progress.member_id == member_id)
    return q.all()


@router.put("", response_model=ProgressOut)
def upsert_progress(
    payload: ProgressUpsert,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER, MemberRole.PRESENTER)),
):
    challenge = (
        db.query(Challenge)
        .filter(Challenge.id == payload.challenge_id, Challenge.tenant_id == current.tenant_id)
        .first()
    )
    if not challenge:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Challenge not found in this Lab")
    member = (
        db.query(Member).filter(Member.id == payload.member_id, Member.tenant_id == current.tenant_id).first()
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Member not found in this Lab")

    progress = (
        db.query(Progress)
        .filter(Progress.member_id == payload.member_id, Progress.challenge_id == payload.challenge_id)
        .first()
    )
    if not progress:
        progress = Progress(member_id=payload.member_id, challenge_id=payload.challenge_id)
        db.add(progress)

    progress.status = payload.status
    progress.completed_at = payload.completed_at
    progress.note = payload.note
    # Manual entry always wins here; automatic sync (Phase 3) will itself
    # refuse to overwrite a 'manual' record per PRD §4.2.1 step 5.
    progress.detected_by = DetectedBy.MANUAL

    db.commit()
    db.refresh(progress)
    return progress
