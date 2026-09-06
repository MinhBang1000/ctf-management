import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    """§19 — immutable audit trail. Deliberately NOT foreign-keyed to
    tenants/members with a cascading delete: an audit record must outlive
    the Lab or account it describes (including the deletion event itself),
    so tenant_id/actor_id are plain UUID columns, not FKs. Never write a
    password, API key, SMTP password, JWT, or reset token into `summary`."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # NULL only for actions with no single Lab context (there are none yet
    # in practice — every action in scope is either inside one Lab or is a
    # Super Admin action *about* one Lab — but left nullable rather than
    # forcing a fake tenant_id if that ever changes).
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "member" | "super_admin"
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # Snapshot, not a join target — stays correct even if the actor account
    # is later deleted.
    actor_label: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
