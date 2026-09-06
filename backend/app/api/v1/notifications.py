import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_member, get_db
from app.models.member import Member
from app.models.notification import Notification
from app.schemas.notification import NotificationOut
from app.services.notification_service import mark_all_read

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _query(db: Session, current: Member):
    return db.query(Notification).filter(
        Notification.tenant_id == current.tenant_id,
        Notification.recipient_member_id == current.id,
        Notification.dismissed_at.is_(None),
    )


@router.get("", response_model=list[NotificationOut])
def list_notifications(db: Session = Depends(get_db), current: Member = Depends(get_current_member)):
    """§12 — scoped to tenant AND the specific recipient (see
    Notification's docstring: one row per event per Lab Leader), never
    another Member's or another Lab's notifications."""
    return _query(db, current).order_by(Notification.created_at.desc()).limit(50).all()


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_one_read(
    notification_id: uuid.UUID, db: Session = Depends(get_db), current: Member = Depends(get_current_member)
):
    notification = _query(db, current).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    notification.read_at = notification.read_at or datetime.now(timezone.utc)
    db.commit()
    db.refresh(notification)
    return notification


@router.post("/read-all")
def mark_all_read_endpoint(db: Session = Depends(get_db), current: Member = Depends(get_current_member)):
    count = mark_all_read(db, current.tenant_id, current.id)
    db.commit()
    return {"marked_read": count}


@router.post("/{notification_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_notification(
    notification_id: uuid.UUID, db: Session = Depends(get_db), current: Member = Depends(get_current_member)
):
    notification = _query(db, current).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    notification.dismissed_at = datetime.now(timezone.utc)
    db.commit()
