from __future__ import annotations

from typing import Any

from alcove.dashboard import DashboardModule
from alcove.home import AlcoveHome
from alcove.usage import UsageRecorder


class ServiceTickFinalizer:
    def __init__(self, home: AlcoveHome) -> None:
        self.home = home

    def finalize(self, payload: dict[str, Any], *, retention_days: int) -> dict[str, Any]:
        usage = UsageRecorder(self.home)
        payload["usage"] = usage.write_rollups()
        payload["prune"] = usage.prune(retention_days=retention_days)
        DashboardModule(self.home).build(build_frontend=False)
        usage.record_action(
            surface="service",
            area="service",
            action="service.tick",
            summary="Ran Alcove service tick",
            metrics=self._metrics(payload),
            visible=False,
        )
        return payload

    @classmethod
    def _metrics(cls, payload: dict[str, Any]) -> dict[str, int]:
        tasks = cls._section(payload, "tasks")
        task_notifications = cls._section(payload, "task_notifications")
        connectors = cls._section(payload, "connectors")
        watchers = cls._section(payload, "watchers")
        blogs = cls._section(payload, "blogs")
        radars = cls._section(payload, "radars")
        automations = cls._section(payload, "automations")
        publishers = cls._section(payload, "publishers")
        mounts = cls._section(payload, "mounts")
        return {
            "routine_tasks": cls._int_value(tasks.get("materialized")),
            "task_notifications": cls._int_value(task_notifications.get("sent")),
            "connector_refreshed": cls._int_value(connectors.get("refreshed")),
            "watcher_changed": cls._int_value(watchers.get("changed")),
            "blog_new": cls._int_value(blogs.get("new")),
            "radar_ran": cls._int_value(radars.get("ran")),
            "automation_ran": cls._int_value(automations.get("ran")),
            "automation_failed": cls._int_value(automations.get("failed")),
            "publisher_ran": cls._int_value(publishers.get("ran")),
            "publisher_updated": cls._int_value(publishers.get("updated")),
            "mounts_refreshed": cls._int_value(mounts.get("refreshed")),
        }

    @staticmethod
    def _section(payload: dict[str, Any], key: str) -> dict[str, Any]:
        value = payload.get(key)
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _int_value(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
