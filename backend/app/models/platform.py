import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import EncryptedJSON


class Platform(Base):
    __tablename__ = "platforms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    adapter_type: Mapped[str] = mapped_column(String(50), nullable=False, default="rootme")
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_focus: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Encrypted at rest (Fernet, PLATFORM_SECRET_KEY) — e.g. {"api_key": "..."}
    # for the Root Me adapter. Never included in any API response schema.
    auth_config: Mapped[dict | None] = mapped_column(EncryptedJSON, nullable=True)
    # §7 — set only by a real successful Test Connection call, never just
    # by "auth_config is non-empty". Reset to NULL whenever auth_config,
    # base_url, or adapter_type changes (see update_platform) — no
    # additional secret is stored here, just the timestamp of proof.
    credentials_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def has_credentials(self) -> bool:
        return bool(self.auth_config)
