import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReminderLog(Base):
    """One row per (member, challenge, milestone) that has ever been
    generated — its mere existence is the dedup guard preventing the same
    T-3/T-1 reminder from being generated twice, regardless of `status`.

    `status` distinguishes what happened to it:
      - "sent": delivered (the only status that ever existed before Lab
        Leader-configurable auto-send/manual-review — every pre-existing
        row is this).
      - "pending": generated but not sent yet (reminder_auto_send=False on
        TenantAutomationSettings) — sitting in the review queue for a Lab
        Leader to read/edit/send.
      - "failed": a send attempt (manual or automatic) raised an email
        error — retryable via the same send endpoint, same shape as
        ReportSendAttempt's failed/retry story.
    """

    __tablename__ = "reminder_logs"
    # No direct tenant_id column: follows the PRD §5 ERD literally, scoped
    # indirectly via member_id/challenge_id. See app/models/progress.py.
    __table_args__ = (
        UniqueConstraint("member_id", "challenge_id", "milestone", name="uq_reminder_member_challenge_milestone"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    challenge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # "T-3" / "T-1" — added in Phase 4 (not in the original §5 ERD): without
    # this, a T-3 send and a T-1 send for the same Member+Challenge are
    # indistinguishable, so duplicate-prevention can't tell them apart.
    milestone: Mapped[str] = mapped_column(String(10), nullable=False)
    channel: Mapped[str] = mapped_column(String(50), nullable=False, default="email")

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="sent")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # NULL until an actual send succeeds — every row created before this
    # column existed already represents a real send, so its old value
    # (this column's original name/semantics) is preserved as-is.
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Rendered content snapshot — populated whether pending, sent, or
    # failed, using whichever template (custom or default) was active at
    # generation time, so history stays accurate even if the template is
    # edited afterward.
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Email of the Lab Leader who manually sent it, or "system:auto-send"
    # for the dispatcher's own automatic path — same audit shape as
    # ReportSendAttempt.attempted_by_email.
    attempted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
