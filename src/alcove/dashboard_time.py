from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

DASHBOARD_TIMEZONE = timezone(timedelta(hours=8))


def dashboard_time_iso(value: str) -> str:
    if not value:
        return ""
    try:
        normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(DASHBOARD_TIMEZONE).isoformat(timespec="seconds")
