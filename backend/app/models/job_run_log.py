import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JobRunLog(Base):
    """Phase 6: per-tenant run history for scheduled jobs that don't
    already have one — reminders and weekly reports only ever logged to
    Python's logger before this, so there was no queryable history to
    alert on. Sync already has sync_log; this doesn't duplicate that."""

    __tablename__ = "job_run_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "reminder" | "weekly_report"
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # "ok" | "error"
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
