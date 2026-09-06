import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlatformFeedback(Base):
    """Free-text feedback about the HSLab CTF Classroom platform itself
    (not Lab-specific data), submitted by any Member (any role) and
    reviewed by the Super Admin from the Console.

    Deliberately NOT foreign-keyed to tenants/members with a cascading
    delete, same reasoning as AuditLog: feedback about the platform is
    worth keeping even if the Lab or account that submitted it is later
    deleted — tenant_id/member_id are plain UUID columns, with
    tenant_name/member_email/member_role snapshotted at submission time
    so the Console listing stays meaningful either way.
    """

    __tablename__ = "platform_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    tenant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    member_email: Mapped[str] = mapped_column(String(255), nullable=False)
    member_role: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
