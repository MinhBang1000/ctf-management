import uuid

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.member import Member
from app.models.super_admin import SuperAdmin


def record_audit(
    db: Session,
    *,
    tenant_id: uuid.UUID | None,
    actor: Member | SuperAdmin,
    action: str,
    summary: str,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
) -> None:
    """§19 — queues one immutable audit row. Deliberately does NOT call
    db.commit() itself: it's meant to ride along in the same transaction
    as the action it describes (call this before the caller's own
    db.commit()), so an audit record can never exist for a change that
    didn't actually happen, or vice versa.

    Never pass a password, API key, SMTP password, JWT, or reset token in
    `summary` — it's a plain-text field with no redaction of its own.
    """
    actor_type = "member" if isinstance(actor, Member) else "super_admin"
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_type=actor_type,
            actor_id=actor.id,
            actor_label=actor.email,
            action=action,
            target_type=target_type,
            target_id=target_id,
            summary=summary,
        )
    )
