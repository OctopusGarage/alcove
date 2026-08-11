from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
import fcntl
import json
from pathlib import Path
from typing import Any

from alcove.home import AlcoveHome
from alcove.notification_delivery import combined_notification_status
from alcove.notifications import send_feishu_message, send_telegram_message
from alcove.service_task_health import (
    TASK_HEALTH_NOTIFICATION_VERSION,
    task_health_notification_should_send,
    task_health_notification_text,
)


class ServiceTaskHealthNotifier:
    def __init__(self, home: AlcoveHome) -> None:
        self.home = home

    def notify_once_per_day(
        self, task_health: dict[str, Any], *, tick_time: datetime
    ) -> dict[str, Any]:
        day = tick_time.date().isoformat()
        with self._state_lock():
            state = self._load_state()
            notifications = state.get("task_health_notifications")
            notification_state = notifications if isinstance(notifications, dict) else {}
            if not task_health_notification_should_send(notification_state.get(day), task_health):
                return {"status": "skipped", "reason": "already_sent", "day": day}

            title = f"Alcove task health: {day}"
            text = task_health_notification_text(task_health, day=day)
            results = {
                "telegram": send_telegram_message(home=self.home, text=text),
                "feishu": send_feishu_message(home=self.home, sink={}, title=title, text=text),
            }
            status = combined_notification_status(results)
            if status in {"sent", "partial"}:
                notification_state[day] = {
                    "status": "sent",
                    "version": TASK_HEALTH_NOTIFICATION_VERSION,
                    "task_health_status": str(task_health.get("status") or "unknown"),
                }
                state["task_health_notifications"] = notification_state
                self._save_state(state)
            return {"status": status, "day": day, "sinks": results}

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

    @contextmanager
    def _state_lock(self) -> Iterator[None]:
        path = self._state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.with_suffix(path.suffix + ".lock")
        with lock_path.open("a+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
