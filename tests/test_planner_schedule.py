from __future__ import annotations

from datetime import date

import pytest

from alcove.planner_schedule import RoutineSchedulePlan


def test_routine_schedule_plan_normalizes_weekly_schedule_and_advances() -> None:
    plan = RoutineSchedulePlan.from_raw(
        {"frequency": "weekly", "interval": 2, "weekdays": ["fri", "wed", "wed"]}
    )

    assert plan.as_dict() == {"frequency": "weekly", "interval": 2, "weekdays": ["wed", "fri"]}
    assert plan.every_days == 14
    assert plan.advance_after(date(2026, 7, 8)) == date(2026, 7, 10)
    assert plan.advance_after(date(2026, 7, 10)) == date(2026, 7, 22)
    assert plan.next_due_on_or_after(date(2026, 7, 12)) == date(2026, 7, 15)


def test_weekly_schedule_next_due_on_or_after_keeps_current_due_weekday() -> None:
    plan = RoutineSchedulePlan.from_raw(
        {"frequency": "weekly", "interval": 2, "weekdays": ["wed", "fri"]}
    )

    assert plan.next_due_on_or_after(date(2026, 7, 8)) == date(2026, 7, 8)
    assert plan.next_due_on_or_after(date(2026, 7, 9)) == date(2026, 7, 10)
    assert plan.next_due_on_or_after(date(2026, 7, 11)) == date(2026, 7, 15)


def test_routine_schedule_plan_preserves_legacy_every_days_items() -> None:
    plan = RoutineSchedulePlan.from_item({"every_days": 3})

    assert plan.as_dict() == {"frequency": "daily", "interval": 3}
    assert plan.every_days == 3
    assert plan.advance_after(date(2026, 7, 8)) == date(2026, 7, 11)


def test_monthly_schedule_keeps_month_end_across_year_and_leap_day() -> None:
    plan = RoutineSchedulePlan.from_raw({"frequency": "monthly", "interval": 1, "day_of_month": 31})

    assert plan.advance_after(date(2027, 12, 31)) == date(2028, 1, 31)
    assert plan.advance_after(date(2028, 1, 31)) == date(2028, 2, 29)
    assert plan.next_due_on_or_after(date(2028, 2, 29)) == date(2028, 2, 29)
    assert plan.next_due_on_or_after(date(2028, 3, 1)) == date(2028, 3, 31)


@pytest.mark.parametrize(
    ("schedule", "message"),
    [
        ({"frequency": "weekly", "weekdays": []}, "weekly schedule requires weekdays"),
        (
            {"frequency": "monthly", "day_of_month": 32},
            "monthly schedule requires day_of_month in 1..31",
        ),
        ({"frequency": "yearly"}, "Unsupported routine schedule frequency: yearly"),
    ],
)
def test_invalid_routine_schedules_fail_with_actionable_error(schedule, message) -> None:
    with pytest.raises(ValueError) as exc_info:
        RoutineSchedulePlan.from_raw(schedule)
    assert str(exc_info.value) == message
