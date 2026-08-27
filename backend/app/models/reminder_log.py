import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReminderLog(Base):
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
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    channel: Mapped[str] = mapped_column(String(50), nullable=False, default="email")
