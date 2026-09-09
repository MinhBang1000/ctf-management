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


class AutomationSettingsOut(BaseModel):
    reminder: RepeatScheduleOut
    weekly_report: RepeatScheduleOut
    weekly_report_auto_send: bool
