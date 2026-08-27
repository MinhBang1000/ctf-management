import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import EncryptedJSON


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Encrypted at rest (Fernet, PLATFORM_SECRET_KEY) — same EncryptedJSON
    # type built for Platform.auth_config in Phase 2, reused here rather
    # than a second encryption approach for the same kind of problem.
    smtp_config: Mapped[dict | None] = mapped_column(EncryptedJSON, nullable=True)
    # Added in Phase 4 (not in the original §5 ERD): §6.9 requires sending
    # the weekly report to "the professor", but no field anywhere stored
    # that address. This is a convenience default — the approve endpoint
    # still requires the recipient explicitly at send time regardless
    # (design principle #5: nothing leaves the Lab without an explicit act).
    professor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def has_smtp_credentials(self) -> bool:
        return bool(self.smtp_config)
