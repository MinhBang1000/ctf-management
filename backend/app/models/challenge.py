import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Challenge(Base):
    __tablename__ = "challenges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    semester_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("semesters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platforms.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # No uniqueness constraint on (semester, week_number): a week may have
    # several parallel challenges (PRD §9 open question 3, resolved: multiple allowed).
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(50), nullable=True)
    external_challenge_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # §1 — canonical Root Me webpage URL (not the API endpoint), for the
    # "Open in Root Me" action. Populated from search results when Root Me
    # provides one, or entered/corrected manually otherwise.
    external_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    presenter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="SET NULL"), nullable=True, index=True
    )
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    points: Mapped[int | None] = mapped_column(Integer, nullable=True)
