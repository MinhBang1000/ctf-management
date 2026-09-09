import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.models.challenge import Challenge
from app.models.member import Member, MemberRole
from app.models.reminder_log import ReminderLog
from app.models.tenant import Tenant
from app.schemas.reminder import PendingReminderOut, ReminderUpdate
from app.services.email_service import EmailConfigError, EmailSendError
from app.services.reminder_service import send_one_pending_reminder

router = APIRouter(prefix="/reminders", tags=["reminders"])


def _query(db: Session, tenant_id: uuid.UUID):
    # ReminderLog has no direct tenant_id (see its own docstring) — scoped
    # via challenge_id, same app-level double-check as RLS's own
    # reminder_logs_tenant_all policy, not relying on RLS alone.
    return (
        db.query(ReminderLog, Member, Challenge)
        .join(Member, Member.id == ReminderLog.member_id)
        .join(Challenge, Challenge.id == ReminderLog.challenge_id)
        .filter(Challenge.tenant_id == tenant_id)
    )


def _out(row: ReminderLog, member: Member, challenge: Challenge) -> PendingReminderOut:
    return PendingReminderOut(
        id=row.id, member_id=member.id, member_name=member.full_name, member_email=member.email,
        challenge_id=challenge.id, challenge_title=challenge.title, milestone=row.milestone,
        status=row.status, subject=row.subject, body=row.body, error_detail=row.error_detail,
        created_at=row.created_at, sent_at=row.sent_at,
    )


def _get_or_404(db: Session, tenant_id: uuid.UUID, reminder_id: uuid.UUID) -> tuple[ReminderLog, Member, Challenge]:
    row = _query(db, tenant_id).filter(ReminderLog.id == reminder_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    return row


@router.get("/pending", response_model=list[PendingReminderOut])
def list_pending_reminders(
    db: Session = Depends(get_db), current: Member = Depends(require_roles(MemberRole.LAB_LEADER))
):
    """Reminders generated with reminder_auto_send off — "pending" (never
    sent yet) and "failed" (a send attempt errored, retryable) both show
    up here; "sent" ones don't (see the audit log / this Member's own
    email for that history)."""
    rows = (
        _query(db, current.tenant_id)
        .filter(ReminderLog.status.in_(["pending", "failed"]))
        .order_by(ReminderLog.created_at.desc())
        .all()
    )
    return [_out(r, m, c) for r, m, c in rows]


@router.patch("/{reminder_id}", response_model=PendingReminderOut)
def update_pending_reminder(
    reminder_id: uuid.UUID,
    payload: ReminderUpdate,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    row, member, challenge = _get_or_404(db, current.tenant_id, reminder_id)
    if row.status == "sent":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot edit a reminder that was already sent")
    row.subject = payload.subject
    row.body = payload.body
    db.commit()
    db.refresh(row)
    return _out(row, member, challenge)


@router.post("/{reminder_id}/send", response_model=PendingReminderOut)
def send_pending_reminder(
    reminder_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    """Sends one pending (or retries one failed) reminder right now,
    exactly as edited — works the same way whether this is its first
    send attempt or a retry after a previous failure."""
    row, member, challenge = _get_or_404(db, current.tenant_id, reminder_id)
    if row.status == "sent":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This reminder was already sent")
    tenant = db.get(Tenant, current.tenant_id)
    try:
        send_one_pending_reminder(db, row, tenant, attempted_by=current.email)
    except (EmailConfigError, EmailSendError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    db.refresh(row)
    return _out(row, member, challenge)


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def discard_pending_reminder(
    reminder_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    """Discards a pending/failed reminder without sending it. Deletes the
    row entirely (not just marking it dismissed) — frees up the
    (member, challenge, milestone) dedup slot, so if the underlying
    condition is still true next time reminders run, it'll be queued
    again rather than being permanently silenced by one dismissal."""
    row, _member, _challenge = _get_or_404(db, current.tenant_id, reminder_id)
    if row.status == "sent":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot discard a reminder that was already sent")
    db.delete(row)
    db.commit()
