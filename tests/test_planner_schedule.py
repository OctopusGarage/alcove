from __future__ import annotations

from datetime import date

from alcove.planner_schedule import RoutineSchedulePlan


def test_routine_schedule_plan_normalizes_weekly_schedule_and_advances() -> None:
    plan = RoutineSchedulePlan.from_raw(
        {"frequency": "weekly", "interval": 2, "weekdays": ["fri", "wed", "wed"]}
    )

    assert plan.as_dict() == {"frequency": "weekly", "interval": 2, "weekdays": ["wed", "fri"]}
    assert plan.every_days == 14
    assert plan.advance_after(date(2026, 7, 8)) == date(2026, 7, 10)
    assert plan.next_due_on_or_after(date(2026, 7, 12)) == date(2026, 7, 15)


def test_routine_schedule_plan_preserves_legacy_every_days_items() -> None:
    plan = RoutineSchedulePlan.from_item({"every_days": 3})

    assert plan.as_dict() == {"frequency": "daily", "interval": 3}
    assert plan.every_days == 3
    assert plan.advance_after(date(2026, 7, 8)) == date(2026, 7, 11)
