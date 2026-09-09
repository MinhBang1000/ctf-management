from datetime import time

from pydantic import BaseModel, Field, model_validator

from app.services.automation_schedule import VALID_REPEATS


class RepeatScheduleIn(BaseModel):
    enabled: bool
    repeat: str
    time_of_day: time
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    interval_days: int | None = Field(default=None, ge=1, le=365)

    @model_validator(mode="after")
    def _check_repeat_shape(self):
        if self.repeat not in VALID_REPEATS:
            raise ValueError(f"repeat must be one of {sorted(VALID_REPEATS)}")
        if self.repeat in ("weekly", "biweekly") and self.day_of_week is None:
            raise ValueError(f"day_of_week is required when repeat={self.repeat!r}")
        if self.repeat == "monthly" and self.day_of_month is None:
            raise ValueError("day_of_month is required when repeat='monthly'")
        if self.repeat == "custom" and self.interval_days is None:
            raise ValueError("interval_days is required when repeat='custom'")
        return self


class RepeatScheduleOut(RepeatScheduleIn):
    last_fired_at: str  # ISO datetime — informational only, not editable


class AutomationSettingsUpdate(BaseModel):
    reminder: RepeatScheduleIn
    weekly_report: RepeatScheduleIn
    weekly_report_auto_send: bool
    # True (default, matches TenantAutomationSettings.reminder_auto_send)
    # sends reminders straight to Members, same as always. False routes
    # them into the pending-reminders review queue instead (see
    # app/api/v1/reminders.py).
    reminder_auto_send: bool = True
    # None/empty string means "use the built-in default" — see
    # ReminderTemplatePreview for what that default actually renders to.
    reminder_subject_template: str | None = Field(default=None, max_length=500)
    reminder_body_template: str | None = None


class AutomationSettingsOut(BaseModel):
    reminder: RepeatScheduleOut
    weekly_report: RepeatScheduleOut
    weekly_report_auto_send: bool
    reminder_auto_send: bool
    reminder_subject_template: str | None
    reminder_body_template: str | None
    # The actual built-in defaults, so the frontend can show them as
    # placeholder text — the Lab Leader edits starting from what's
    # already being sent, not a blank box.
    default_reminder_subject_template: str
    default_reminder_body_template: str
