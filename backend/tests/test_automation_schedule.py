"""Pure schedule math — no DB, no email, no Root Me. Exhaustive on purpose
since this is the trickiest part of the automation-settings feature."""
from datetime import datetime, time, timedelta, timezone

from app.services.automation_schedule import RepeatSchedule, is_due, next_fire_at


def dt(y, m, d, h=0, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=timezone.utc)


# --- daily -----------------------------------------------------------

def test_daily_next_fire_same_day_if_time_not_passed():
    sched = RepeatSchedule(enabled=True, repeat="daily", time_of_day=time(9, 0))
    assert next_fire_at(sched, dt(2026, 3, 10, 6, 0)) == dt(2026, 3, 10, 9, 0)


def test_daily_next_fire_rolls_to_tomorrow_if_time_passed():
    sched = RepeatSchedule(enabled=True, repeat="daily", time_of_day=time(9, 0))
    assert next_fire_at(sched, dt(2026, 3, 10, 10, 0)) == dt(2026, 3, 11, 9, 0)


def test_daily_is_due_true_once_time_reached():
    sched = RepeatSchedule(enabled=True, repeat="daily", time_of_day=time(9, 0))
    anchor = dt(2026, 3, 9, 9, 0)  # last fired yesterday at 09:00
    assert is_due(sched, dt(2026, 3, 10, 8, 59), anchor) is False
    assert is_due(sched, dt(2026, 3, 10, 9, 0), anchor) is True
    assert is_due(sched, dt(2026, 3, 10, 12, 0), anchor) is True


def test_daily_not_due_twice_same_day():
    sched = RepeatSchedule(enabled=True, repeat="daily", time_of_day=time(9, 0))
    anchor = dt(2026, 3, 10, 9, 0)  # just fired today
    assert is_due(sched, dt(2026, 3, 10, 15, 0), anchor) is False
    assert is_due(sched, dt(2026, 3, 11, 9, 0), anchor) is True


# --- weekly / biweekly -------------------------------------------------

def test_weekly_next_fire_lands_on_target_weekday():
    # 2026-03-10 is a Tuesday (weekday()==1). Target Monday (0).
    sched = RepeatSchedule(enabled=True, repeat="weekly", time_of_day=time(0, 0), day_of_week=0)
    result = next_fire_at(sched, dt(2026, 3, 10, 12, 0))
    assert result.weekday() == 0
    assert result > dt(2026, 3, 10, 12, 0)
    assert (result - dt(2026, 3, 10, 12, 0)).days <= 7


def test_weekly_is_due_exactly_on_first_occurrence_after_anchor():
    sched = RepeatSchedule(enabled=True, repeat="weekly", time_of_day=time(9, 0), day_of_week=0)  # Monday
    anchor = dt(2026, 3, 9, 9, 0)  # a Monday, just fired
    next_monday = dt(2026, 3, 16, 9, 0)
    assert is_due(sched, next_monday - timedelta(minutes=1), anchor) is False
    assert is_due(sched, next_monday, anchor) is True


def test_biweekly_waits_two_weeks_not_one():
    sched = RepeatSchedule(enabled=True, repeat="biweekly", time_of_day=time(9, 0), day_of_week=0)
    anchor = dt(2026, 3, 9, 9, 0)  # Monday, just fired
    one_week_later = dt(2026, 3, 16, 9, 0)
    two_weeks_later = dt(2026, 3, 23, 9, 0)
    assert is_due(sched, one_week_later, anchor) is False
    assert is_due(sched, two_weeks_later, anchor) is True


# --- monthly -------------------------------------------------------------

def test_monthly_next_fire_same_month_if_day_not_passed():
    sched = RepeatSchedule(enabled=True, repeat="monthly", time_of_day=time(9, 0), day_of_month=15)
    assert next_fire_at(sched, dt(2026, 3, 1, 0, 0)) == dt(2026, 3, 15, 9, 0)


def test_monthly_rolls_to_next_month_if_day_passed():
    sched = RepeatSchedule(enabled=True, repeat="monthly", time_of_day=time(9, 0), day_of_month=15)
    assert next_fire_at(sched, dt(2026, 3, 20, 0, 0)) == dt(2026, 4, 15, 9, 0)


def test_monthly_clamps_day_31_in_february():
    sched = RepeatSchedule(enabled=True, repeat="monthly", time_of_day=time(9, 0), day_of_month=31)
    # 2026 is not a leap year -> Feb has 28 days.
    result = next_fire_at(sched, dt(2026, 1, 20, 0, 0))
    assert result == dt(2026, 1, 31, 9, 0)
    result2 = next_fire_at(sched, dt(2026, 2, 1, 0, 0))
    assert result2 == dt(2026, 2, 28, 9, 0)


def test_monthly_december_rolls_into_next_year():
    sched = RepeatSchedule(enabled=True, repeat="monthly", time_of_day=time(9, 0), day_of_month=15)
    result = next_fire_at(sched, dt(2026, 12, 20, 0, 0))
    assert result == dt(2027, 1, 15, 9, 0)


# --- custom interval -------------------------------------------------------

def test_custom_interval_days():
    sched = RepeatSchedule(enabled=True, repeat="custom", time_of_day=time(0, 0), interval_days=3)
    anchor = dt(2026, 3, 10, 9, 0)
    assert next_fire_at(sched, anchor) == dt(2026, 3, 13, 9, 0)
    assert is_due(sched, dt(2026, 3, 12, 9, 0), anchor) is False
    assert is_due(sched, dt(2026, 3, 13, 9, 0), anchor) is True


# --- disabled / never --------------------------------------------------

def test_disabled_never_due():
    sched = RepeatSchedule(enabled=False, repeat="daily", time_of_day=time(0, 0))
    assert is_due(sched, dt(2030, 1, 1), dt(2020, 1, 1)) is False


def test_repeat_never_is_never_due():
    sched = RepeatSchedule(enabled=True, repeat="never", time_of_day=time(0, 0))
    assert is_due(sched, dt(2030, 1, 1), dt(2020, 1, 1)) is False


def test_no_retroactive_catch_up_on_first_enable():
    """A schedule created (anchor = creation time) after its target time
    already passed this cycle must NOT fire immediately — the first real
    fire is the next natural occurrence, not a catch-up for a slot that
    passed before the schedule existed."""
    sched = RepeatSchedule(enabled=True, repeat="daily", time_of_day=time(6, 0))
    created_at = dt(2026, 3, 10, 20, 0)  # created well after today's 06:00 slot
    assert is_due(sched, dt(2026, 3, 10, 23, 0), created_at) is False
    assert is_due(sched, dt(2026, 3, 11, 6, 0), created_at) is True
