import uuid
from datetime import datetime, time

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Time, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Matches the previous system-wide .env defaults (REMINDER_CHECK_HOUR_UTC=6,
# WEEKLY_REPORT_DAY_OF_WEEK=1/Tuesday, WEEKLY_REPORT_HOUR_UTC=0) so migrating
# an existing Lab to per-Lab settings doesn't silently change when its
# automation runs.
DEFAULT_REMINDER_TIME = time(6, 0)
DEFAULT_WEEKLY_REPORT_TIME = time(0, 0)
DEFAULT_WEEKLY_REPORT_DAY_OF_WEEK = 1


class TenantAutomationSettings(Base):
    """Per-Lab schedule for the two repeating automation tasks (reminders,
    weekly report). One row per Tenant, created lazily on first read/write
    (see get_or_create_automation_settings) rather than at Lab-creation
    time, so a Lab created before this feature existed still gets sane
    defaults the first time anyone touches its settings.

    Semester report is NOT here — see Semester.report_trigger_date, a
    single-date trigger rather than a repeating schedule.

    `*_last_fired_at` doubles as the schedule's "anchor" for
    app.services.automation_schedule.is_due(): defaulted to `now()` at row
    creation, so a schedule never retroactively catches up on a slot that
    passed before it existed (see that module's own docstring).
    """

    __tablename__ = "tenant_automation_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    reminder_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reminder_repeat: Mapped[str] = mapped_column(String(20), nullable=False, default="daily")
    reminder_time_of_day: Mapped[time] = mapped_column(Time, nullable=False, default=DEFAULT_REMINDER_TIME)
    reminder_day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reminder_day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reminder_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reminder_last_fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    weekly_report_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    weekly_report_repeat: Mapped[str] = mapped_column(String(20), nullable=False, default="weekly")
    weekly_report_time_of_day: Mapped[time] = mapped_column(Time, nullable=False, default=DEFAULT_WEEKLY_REPORT_TIME)
    weekly_report_day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True, default=DEFAULT_WEEKLY_REPORT_DAY_OF_WEEK)
    weekly_report_day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weekly_report_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weekly_report_auto_send: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    weekly_report_last_fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
