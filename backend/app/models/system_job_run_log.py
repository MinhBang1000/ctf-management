import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SystemJobRunLog(Base):
    """§8 — history for jobs with no single-Tenant scope (currently: the
    full-database backup). Deliberately separate from JobRunLog (which is
    always one Tenant's reminder/weekly_report run) rather than making
    tenant_id nullable there — keeps "this table is always Tenant-scoped"
    true for every RLS policy that assumes it. Super-Admin-only, matching
    §8's "system-wide operational visibility restricted to Super Admins."
    """

    __tablename__ = "system_job_run_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "backup"
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # "ok" | "error"
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
