import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.member import Member, MemberRole
from app.models.notification import Notification


def notify_lab_leaders(
    db: Session,
    tenant_id: uuid.UUID,
    type: str,
    title: str,
    body: str | None = None,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    dedupe: bool = True,
) -> None:
    """§12 — one persistent Notification row per active Lab Leader in the
    tenant (see Notification's own docstring for why one-row-per-recipient
    rather than a separate reads table). Every current notification-worthy
    event (report ready, semester-ended nudge, sync error) is Lab-Leader-
    facing, so that's the only recipient set this needs today.

    dedupe=True (the default) skips creating a duplicate when an
    undismissed notification with the same (tenant, recipient, type,
    target_type, target_id) already exists — used for events that would
    otherwise re-fire every time a periodic check runs (e.g. "this
    semester still has no report") rather than exactly once when the
    underlying condition first became true.
    """
    leaders = (
        db.query(Member)
        .filter(Member.tenant_id == tenant_id, Member.role == MemberRole.LAB_LEADER, Member.active.is_(True))
        .all()
    )
    for leader in leaders:
        if dedupe:
            existing = (
                db.query(Notification)
                .filter(
                    Notification.tenant_id == tenant_id,
                    Notification.recipient_member_id == leader.id,
                    Notification.type == type,
                    Notification.target_type == target_type,
                    Notification.target_id == target_id,
                    Notification.dismissed_at.is_(None),
                )
                .first()
            )
            if existing:
                continue
        db.add(
            Notification(
                tenant_id=tenant_id,
                recipient_member_id=leader.id,
                type=type,
                title=title,
                body=body,
                target_type=target_type,
                target_id=target_id,
            )
        )


def mark_read(db: Session, notification: Notification) -> None:
    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)


def mark_all_read(db: Session, tenant_id: uuid.UUID, recipient_member_id: uuid.UUID) -> int:
    return (
        db.query(Notification)
        .filter(
            Notification.tenant_id == tenant_id,
            Notification.recipient_member_id == recipient_member_id,
            Notification.read_at.is_(None),
        )
        .update({Notification.read_at: datetime.now(timezone.utc)})
    )
