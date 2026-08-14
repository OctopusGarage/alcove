from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, time, timedelta
import calendar
from typing import Any

from alcove.markdown import normalize_slug


WEEKDAY_ORDER = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
DIGEST_WEEKDAYS = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}


@dataclass(frozen=True)
class RoutineSchedulePlan:
    schedule: dict[str, Any]

    @classmethod
    def from_raw(cls, schedule: dict[str, Any]) -> RoutineSchedulePlan:
        return cls(_normalize_routine_schedule(schedule))

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> RoutineSchedulePlan:
        raw = item.get("schedule")
        if isinstance(raw, dict) and raw:
            return cls.from_raw(raw)
        every_days = _positive_int(item.get("every_days"), default=1)
        return cls.from_raw({"frequency": "daily", "interval": every_days})

    def as_dict(self) -> dict[str, Any]:
        return dict(self.schedule)

    @property
    def frequency(self) -> str:
        return str(self.schedule.get("frequency") or "daily")

    @property
    def interval(self) -> int:
        return _positive_int(self.schedule.get("interval"), default=1)

    @property
    def every_days(self) -> int:
        if self.frequency == "weekly":
            return self.interval * 7
        if self.frequency == "monthly":
            return self.interval * 30
        return self.interval

    def advance_after(self, current_due: date) -> date:
        if self.frequency == "daily":
            return current_due + timedelta(days=self.interval)
        if self.frequency == "weekly":
            weekdays = [WEEKDAY_ORDER[day] for day in _list(self.schedule.get("weekdays"))]
            current_weekday = current_due.weekday()
            for weekday in weekdays:
                if weekday > current_weekday:
                    return current_due + timedelta(days=weekday - current_weekday)
            week_start = current_due - timedelta(days=current_weekday)
            return week_start + timedelta(weeks=self.interval, days=weekdays[0])
        day_of_month = int(self.schedule.get("day_of_month") or 1)
        month = current_due.month
        year = current_due.year
        for _ in range(self.interval):
            month += 1
            if month == 13:
                month = 1
                year += 1
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, min(day_of_month, last_day))

    def next_due_on_or_after(self, current: date) -> date:
        if self.frequency == "monthly":
            day_of_month = int(self.schedule.get("day_of_month") or 1)
            last_day = calendar.monthrange(current.year, current.month)[1]
            current_month_due = date(current.year, current.month, min(day_of_month, last_day))
            if current <= current_month_due:
                return current_month_due
            return self.advance_after(current_month_due)
        probe = current - timedelta(days=1)
        if self.frequency == "weekly":
            weekdays = [WEEKDAY_ORDER[day] for day in _list(self.schedule.get("weekdays"))]
            for offset in range(7):
                candidate = current + timedelta(days=offset)
                if candidate.weekday() in weekdays:
                    return candidate
        next_due = self.advance_after(probe)
        while next_due < current:
            next_due = self.advance_after(next_due)
        return next_due


def validate_routine_schedule(schedule: dict[str, Any]) -> dict[str, Any]:
    return RoutineSchedulePlan.from_raw(schedule).as_dict()


def _normalize_routine_schedule(schedule: dict[str, Any]) -> dict[str, Any]:
    frequency = normalize_slug(str(schedule.get("frequency") or "daily"))
    interval = _positive_int(schedule.get("interval"), default=1)
    normalized: dict[str, Any] = {"frequency": frequency, "interval": interval}
    if frequency == "daily":
        return normalized
    if frequency == "weekly":
        weekdays = [normalize_slug(str(day)) for day in _list(schedule.get("weekdays"))]
        if not weekdays or any(day not in WEEKDAY_ORDER for day in weekdays):
            raise ValueError("weekly schedule requires weekdays")
        normalized["weekdays"] = sorted(set(weekdays), key=lambda day: WEEKDAY_ORDER[day])
        return normalized
    if frequency == "monthly":
        day_of_month = int(schedule.get("day_of_month") or 0)
        if day_of_month < 1 or day_of_month > 31:
            raise ValueError("monthly schedule requires day_of_month in 1..31")
        normalized["day_of_month"] = day_of_month
        return normalized
    raise ValueError(f"Unsupported routine schedule frequency: {frequency}")


def routine_schedule_from_item(item: dict[str, Any]) -> dict[str, Any]:
    return RoutineSchedulePlan.from_item(item).as_dict()


def schedule_every_days(schedule: dict[str, Any]) -> int:
    return RoutineSchedulePlan.from_raw(schedule).every_days


def advance_next_due(schedule: dict[str, Any], current_due: date) -> date:
    return RoutineSchedulePlan.from_raw(schedule).advance_after(current_due)


def next_due_on_or_after(schedule: dict[str, Any], current: date) -> date:
    return RoutineSchedulePlan.from_raw(schedule).next_due_on_or_after(current)


def digest_due(
    period: str,
    policy: dict[str, Any],
    current: date,
    *,
    current_time: time | None = None,
) -> bool:
    normalized = normalize_slug(period)
    if normalized == "daily":
        return digest_time_due(policy, current_time=current_time)
    if normalized == "weekly":
        day = normalize_slug(str(policy.get("day") or "sunday"))
        return current.weekday() == DIGEST_WEEKDAYS.get(day, 6) and digest_time_due(
            policy,
            current_time=current_time,
        )
    return False


def digest_time_due(policy: dict[str, Any], *, current_time: time | None = None) -> bool:
    raw_time = str(policy.get("time") or policy.get("at") or "").strip()
    if not raw_time or current_time is None:
        return True
    parts = raw_time.split(":", 1)
    if len(parts) != 2:
        return True
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return True
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return True
    return (current_time.hour, current_time.minute) >= (hour, minute)


def digest_state_key(period: str, current: date) -> str:
    normalized = normalize_slug(period)
    if normalized == "weekly":
        year, week, _ = current.isocalendar()
        return f"digest:{normalized}:{year}-W{week:02d}"
    return f"digest:{normalized}:{current.isoformat()}"


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple | set):
        return list(value)
    if isinstance(value, Iterable) and not isinstance(value, str):
        return list(value)
    return [value]


def _positive_int(value: Any, *, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default
