"""Pure date/time math for the Apple-Reminders-style per-Lab automation
schedules (reminders, weekly report). Deliberately has zero DB/Celery/
network dependency — every rule here is a plain function of
(schedule, anchor/now), so it's exhaustively unit-testable without a
database, and the dispatcher task (app/tasks/automation_dispatcher.py) is
just "call is_due(), and if true, do the real work and stamp
last_fired_at."

Semester report is NOT handled here — it's a single date trigger, not a
repeating schedule (see Semester.report_trigger_date), simple enough to
check directly in the dispatcher without needing this module's machinery.
"""
import calendar
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

REPEAT_NEVER = "never"
REPEAT_DAILY = "daily"
REPEAT_WEEKLY = "weekly"
REPEAT_BIWEEKLY = "biweekly"
REPEAT_MONTHLY = "monthly"
REPEAT_CUSTOM = "custom"

VALID_REPEATS = {REPEAT_NEVER, REPEAT_DAILY, REPEAT_WEEKLY, REPEAT_BIWEEKLY, REPEAT_MONTHLY, REPEAT_CUSTOM}


@dataclass(frozen=True)
class RepeatSchedule:
    """One task's schedule, Apple-Reminders style. Only the fields that
    apply to `repeat` need be set:
      - daily: none of the below needed.
      - weekly / biweekly: day_of_week (0=Monday .. 6=Sunday).
      - monthly: day_of_month (1-31; clamped to the last real day of a
        shorter month — e.g. 31 in February means the 28th/29th).
      - custom: interval_days (fire every N days from the anchor).
    """

    enabled: bool
    repeat: str
    time_of_day: time
    day_of_week: int | None = None
    day_of_month: int | None = None
    interval_days: int | None = None


def _combine_utc(d, t: time) -> datetime:
    return datetime(d.year, d.month, d.day, t.hour, t.minute, t.second, tzinfo=timezone.utc)


def _clamped_day_of_month(year: int, month: int, day: int) -> int:
    last_day = calendar.monthrange(year, month)[1]
    return min(day, last_day)


def _next_monthly_occurrence(after: datetime, day_of_month: int, t: time) -> datetime:
    year, month = after.year, after.month
    candidate = _combine_utc(after.date().replace(day=_clamped_day_of_month(year, month, day_of_month)), t)
    if candidate > after:
        return candidate
    month += 1
    if month > 12:
        month = 1
        year += 1
    return _combine_utc(after.date().replace(year=year, month=month, day=_clamped_day_of_month(year, month, day_of_month)), t)


def _next_weekly_occurrence(after: datetime, day_of_week: int, t: time, step_days: int) -> datetime:
    days_ahead = (day_of_week - after.weekday()) % 7
    candidate = _combine_utc((after + timedelta(days=days_ahead)).date(), t)
    if candidate <= after:
        candidate += timedelta(days=step_days)
    return candidate


def next_fire_at(schedule: RepeatSchedule, after: datetime) -> datetime:
    """The next scheduled instant strictly after `after`.

    `after` is always a real instant — either when this schedule last
    actually fired, or (if it never has) the moment it was created/last
    edited. Treating "just created" as equivalent to "just fired" means
    the very first real fire is always the next natural occurrence going
    forward — never a retroactive catch-up for a slot that passed before
    anyone turned the schedule on, which would be a surprising thing to
    have happen the moment a Lab Leader saves a new schedule.
    """
    if schedule.repeat == REPEAT_DAILY:
        candidate = _combine_utc(after.date(), schedule.time_of_day)
        if candidate <= after:
            candidate += timedelta(days=1)
        return candidate
    if schedule.repeat == REPEAT_WEEKLY:
        return _next_weekly_occurrence(after, schedule.day_of_week or 0, schedule.time_of_day, step_days=7)
    if schedule.repeat == REPEAT_BIWEEKLY:
        return _next_weekly_occurrence(after, schedule.day_of_week or 0, schedule.time_of_day, step_days=14)
    if schedule.repeat == REPEAT_MONTHLY:
        return _next_monthly_occurrence(after, schedule.day_of_month or 1, schedule.time_of_day)
    if schedule.repeat == REPEAT_CUSTOM:
        return after + timedelta(days=schedule.interval_days or 1)
    raise ValueError(f"next_fire_at called with repeat={schedule.repeat!r}")


def is_due(schedule: RepeatSchedule, now: datetime, anchor: datetime) -> bool:
    """True if this schedule should fire on the current dispatcher tick.

    `anchor` is the settings row's `*_last_fired_at` column, which the
    model/migration defaults to the row's own creation time — so this
    function never has to guess what "never fired yet" should mean; the
    caller already resolved that into a real instant.
    """
    if not schedule.enabled or schedule.repeat == REPEAT_NEVER:
        return False
    return now >= next_fire_at(schedule, anchor)
