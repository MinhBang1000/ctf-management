import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProgressStatus(str, enum.Enum):
    EARLY = "early"
    DONE = "done"
    LATE = "late"
    MISSING = "missing"


class DetectedBy(str, enum.Enum):
    MANUAL = "manual"
    SYNC = "sync"


class Progress(Base):
    __tablename__ = "progress"
    # No direct tenant_id column: follows the PRD §5 ERD literally.
    # Scoped indirectly via member_id/challenge_id (both tenant-scoped),
    # per §6.6 ("scope theo tenant_id (qua member/challenge)").
    __table_args__ = (UniqueConstraint("member_id", "challenge_id", name="uq_progress_member_challenge"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    challenge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[ProgressStatus] = mapped_column(
        Enum(ProgressStatus, native_enum=False, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=ProgressStatus.MISSING,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    detected_by: Mapped[DetectedBy] = mapped_column(
        Enum(DetectedBy, native_enum=False, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=DetectedBy.MANUAL,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
