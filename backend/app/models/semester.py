import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Semester(Base):
    __tablename__ = "semesters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Semester-report automation: NOT a repeating schedule (see
    # app/services/automation_schedule.py's own docstring on why) — a
    # single date, defaulted to this Semester's own end_date at INSERT
    # time via a context-sensitive Python default (a plain server_default
    # can't reference a sibling column) but independently editable
    # afterward and never re-synced if end_date changes later. Every
    # insert path (API, factories) gets this for free — nothing has to
    # remember to set it explicitly.
    report_trigger_date: Mapped[date] = mapped_column(
        Date, nullable=False, default=lambda ctx: ctx.get_current_parameters()["end_date"]
    )
    report_automation_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Same "draft vs auto-send" choice as weekly report, but independent —
    # a Lab Leader may want to review the final semester report before it
    # reaches the professor even if weekly ones auto-send, or vice versa.
    report_auto_send: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # NULL until the automation dispatcher actually fires it once — after
    # that this Semester's automated trigger never fires again (it's a
    # single date, not a repeating schedule), even if report_trigger_date
    # is edited afterward to a date that's already passed.
    report_last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
