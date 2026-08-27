import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MemberRole(str, enum.Enum):
    LAB_LEADER = "lab_leader"
    PRESENTER = "presenter"
    MEMBER = "member"


class Member(Base):
    __tablename__ = "members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Email is unique system-wide (not just per-tenant): login resolves the
    # user's Lab purely from their email (PRD §6.1), and §2 states one
    # account belongs to exactly one Lab.
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    # Not present in the PRD §5 ERD, but required to support auth (PRD §3.4
    # leaves JWT-vs-session and its implementation details to us).
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[MemberRole] = mapped_column(
        Enum(MemberRole, native_enum=False, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=MemberRole.MEMBER,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    platform_accounts: Mapped[list["MemberPlatformAccount"]] = relationship(
        "MemberPlatformAccount", cascade="all, delete-orphan", passive_deletes=True
    )
