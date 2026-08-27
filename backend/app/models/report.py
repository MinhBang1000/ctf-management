import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    semester_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("semesters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Added in Phase 4 (not in the original §5 ERD): generated_at is when
    # the draft was created; without a separate sent_at there's no real
    # "when was this actually sent" for the audit trail the approve flow
    # needs to preserve.
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Added in Phase 5: the structured aggregation behind a semester
    # report (per-member stats, weekly trend, platform breakdown),
    # captured once at generation time. PDF/Excel export renders this
    # snapshot rather than re-querying, so exports stay consistent with
    # what was actually reviewed/approved even if newer Progress data
    # lands afterward. Not used by type="weekly" reports (NULL there —
    # those only ever had a text body, no export requirement).
    data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
