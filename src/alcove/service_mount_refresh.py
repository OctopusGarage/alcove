from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path
from typing import Any

from alcove.home import AlcoveHome
from alcove.mounts import MountsModule


DEFAULT_MOUNT_REFRESH_DAYS = 2


class ServiceMountRefresh:
    def __init__(self, home: AlcoveHome) -> None:
        self.home = home

    def run(self, *, interval_days: int, today: str) -> dict[str, Any]:
        mount_module = MountsModule(home=self.home)
        mounts = mount_module.list()
        if not mounts:
            return {"status": "skipped", "reason": "no_mounts", "checked": 0, "refreshed": 0}

        interval = max(int(interval_days or DEFAULT_MOUNT_REFRESH_DAYS), 1)
        state = self._load_state()
        stored_mount_state = state.get("mounts")
        mount_state = stored_mount_state if isinstance(stored_mount_state, dict) else {}
        last_refreshed_at = str(mount_state.get("last_refreshed_at") or "")
        now = tick_now(today)
        if not _is_due(last_refreshed_at, now=now, interval_days=interval):
            return {
                "status": "skipped",
                "reason": "not_due",
                "checked": len(mounts),
                "refreshed": 0,
                "last_refreshed_at": last_refreshed_at,
                "next_due_at": _next_due_at(last_refreshed_at, interval),
                "interval_days": interval,
            }

        report = mount_module.scan()
        timestamp = now.isoformat(timespec="seconds")
        payload = {
            "status": "checked",
            "checked": len(mounts),
            "refreshed": len(mounts),
            "last_refreshed_at": timestamp,
            "next_due_at": _next_due_at(timestamp, interval),
            "interval_days": interval,
            "scanned": _int_value(report.get("scanned")),
            "skipped": _int_value(report.get("skipped")),
            "reused": _int_value(report.get("reused")),
            "skip_reasons": report.get("skip_reasons", {}),
        }
        state["mounts"] = {
            "last_refreshed_at": timestamp,
            "refresh_interval_days": interval,
            "last_report": {
                "scanned": payload["scanned"],
                "skipped": payload["skipped"],
                "reused": payload["reused"],
            },
        }
        self._save_state(state)
        return payload

    def _state_path(self) -> Path:
        return self.home.paths().stats / "service-state.json"

    def _load_state(self) -> dict[str, Any]:
        path = self._state_path()
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _save_state(self, state: dict[str, Any]) -> None:
        path = self._state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def tick_now(today: str) -> datetime:
    value = str(today or "").strip()
    if not value:
        return datetime.now(UTC)
    if len(value) == 10:
        return datetime.combine(date.fromisoformat(value), datetime.min.time(), tzinfo=UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _is_due(last_refreshed_at: str, *, now: datetime, interval_days: int) -> bool:
    last = _parse_timestamp(last_refreshed_at)
    if last is None:
        return True
    return now >= last + timedelta(days=interval_days)


def _next_due_at(last_refreshed_at: str, interval_days: int) -> str:
    last = _parse_timestamp(last_refreshed_at)
    if last is None:
        return ""
    return (last + timedelta(days=interval_days)).isoformat(timespec="seconds")


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
