import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MemberPlatformAccount(Base):
    __tablename__ = "member_platform_accounts"
    __table_args__ = (UniqueConstraint("member_id", "platform_id", name="uq_member_platform"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platforms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_username: Mapped[str] = mapped_column(String(255), nullable=False)
    # Root Me id_auteur: a numeric-looking string, NOT a UUID. Required
    # (NOT NULL) per PRD §5 note and §6.3 — must be entered explicitly on
    # the form, never silently auto-derived from external_username.
    external_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
