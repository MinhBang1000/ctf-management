import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TenantDataJob(Base):
    """§17/§18 — tracks one per-Lab export, backup, or restore operation.

    Executed synchronously in v1 (a Lab's full dataset is a few thousand
    rows at most, not a background-worthy volume) but still modeled and
    exposed as a trackable job record from day one, so a later move to a
    real async Celery job doesn't change the API shape or audit trail —
    only how `status` transitions from pending to running get set.
    """

    __tablename__ = "tenant_data_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "export" | "backup" | "restore"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending|running|done|failed
    format_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1")
    requested_by_email: Mapped[str] = mapped_column(String(255), nullable=False)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
