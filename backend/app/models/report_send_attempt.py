import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReportSendAttempt(Base):
    """§10/§11 — every send attempt for a Report (the first approve&send,
    a retry after failure, or a deliberate resend), so "sent successfully"
    vs "failed" vs "retried" vs "resent" is a real queryable history
    instead of only the Report's own single status/sent_at/approved_by."""

    __tablename__ = "report_send_attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    # "initial" | "retry" (after a failure) | "resend" (deliberate re-send
    # of an already successfully-sent report)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # "success" | "failed"
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempted_by_email: Mapped[str] = mapped_column(String(255), nullable=False)
