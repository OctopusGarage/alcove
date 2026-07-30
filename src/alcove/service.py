from __future__ import annotations

from typing import Any

from alcove.application import AlcoveApplication
from alcove.automations import AutomationsModule
from alcove.blog_monitor import BlogMonitorModule
from alcove.dashboard import DashboardModule
from alcove.home import AlcoveHome
from alcove.paths import compact_user_path
from alcove.publisher_dirty import mark_publisher_source_dirty
from alcove.publishers import PublisherModule
from alcove.radars import RadarModule
from alcove.runtime import AlcoveRuntime
from alcove.service_launchd import ServiceLaunchd
from alcove.service_mount_refresh import DEFAULT_MOUNT_REFRESH_DAYS, ServiceMountRefresh, tick_now
from alcove.service_task_health import build_task_health_summary
from alcove.service_task_health_notifications import ServiceTaskHealthNotifier
from alcove.tasks import TasksModule
from alcove.usage import UsageRecorder
from alcove.watchers import WatcherModule


class ServiceModule:
    def __init__(self, home: AlcoveHome) -> None:
        self.home = home
        self.launchd = ServiceLaunchd(home)
        self.mount_refresh = ServiceMountRefresh(home)
        self.task_health_notifier = ServiceTaskHealthNotifier(home)

    def install(
        self,
        *,
        dashboard: bool,
        scheduler: bool,
        host: str = "127.0.0.1",
        port: int = 8765,
        interval_minutes: int = 30,
        load: bool = False,
    ) -> dict[str, Any]:
        return self.launchd.install(
            dashboard=dashboard,
            scheduler=scheduler,
            host=host,
            port=port,
            interval_minutes=interval_minutes,
            load=load,
        )

    def uninstall(
        self, *, dashboard: bool, scheduler: bool, unload: bool = False
    ) -> dict[str, Any]:
        return self.launchd.uninstall(dashboard=dashboard, scheduler=scheduler, unload=unload)

    def status(self, *, dashboard: bool, scheduler: bool) -> dict[str, Any]:
        return self.launchd.status(dashboard=dashboard, scheduler=scheduler)

    def start(self, *, dashboard: bool, scheduler: bool) -> dict[str, Any]:
        return self.launchd.start(dashboard=dashboard, scheduler=scheduler)

    def stop(self, *, dashboard: bool, scheduler: bool) -> dict[str, Any]:
        return self.launchd.stop(dashboard=dashboard, scheduler=scheduler)

    def tick(
        self,
        *,
        retention_days: int = 90,
        refresh_connectors: bool = True,
        check_watchers: bool = True,
        check_blogs: bool = True,
        check_radars: bool = True,
        run_automations: bool = True,
        run_publishers: bool = True,
        refresh_mounts: bool = True,
        mount_refresh_days: int = DEFAULT_MOUNT_REFRESH_DAYS,
        fix_health: bool = True,
        notify_task_health: bool = False,
        today: str = "",
    ) -> dict[str, Any]:
        tick_time = tick_now(today)
        runtime = AlcoveRuntime.from_modules(home=self.home)
        app = AlcoveApplication(runtime)
        usage = UsageRecorder(self.home)
        task_module = TasksModule(home=self.home)
        tasks = task_module.routine_materialize_due(today=today or None)
        if tasks:
            mark_publisher_source_dirty(self.home, "tasks")
        task_notifications = task_module.run_due_notifications(today=today or None)
        connector_payload = (
            app.external.connector_refresh_payload(stale_only=True)
            if refresh_connectors
            else {"status": "skipped"}
        )
        watchers_payload = (
            WatcherModule(self.home).check(stale_only=True)
            if check_watchers
            else {"status": "skipped", "checked": 0}
        )
        blogs_payload = (
            BlogMonitorModule(self.home).check(stale_only=True)
            if check_blogs
            else {"status": "skipped", "checked": 0}
        )
        radars_payload = (
            RadarModule(self.home).check_stale()
            if check_radars
            else {"status": "skipped", "ran": 0, "skipped": 0, "errors": 0}
        )
        automations_payload = (
            AutomationsModule(self.home).run_due()
            if run_automations
            else {"status": "skipped", "ran": 0, "skipped": 0, "failed": 0}
        )
        publishers_payload = (
            PublisherModule(self.home).run_due()
            if run_publishers
            else {"status": "skipped", "ran": 0, "skipped": 0, "updated": 0, "errors": 0}
        )
        mounts_payload = (
            self.mount_refresh.run(interval_days=mount_refresh_days, today=today)
            if refresh_mounts
            else {"status": "skipped", "reason": "disabled", "checked": 0, "refreshed": 0}
        )
        okf_payload = app.system.okf_catalog_build_payload()
        health_payload = app.system.health_payload(fix=fix_health, strict=False)
        usage_payload = usage.write_rollups()
        prune_payload = usage.prune(retention_days=retention_days)
        DashboardModule(self.home).build(build_frontend=False)
        usage.record_action(
            surface="service",
            area="service",
            action="service.tick",
            summary="Ran Alcove service tick",
            metrics={
                "routine_tasks": len(tasks),
                "task_notifications": _int_value(task_notifications.get("sent")),
                "connector_refreshed": int(connector_payload.get("refreshed") or 0),
                "watcher_changed": _int_value(watchers_payload.get("changed")),
                "blog_new": _int_value(blogs_payload.get("new")),
                "radar_ran": _int_value(radars_payload.get("ran")),
                "automation_ran": _int_value(automations_payload.get("ran")),
                "automation_failed": _int_value(automations_payload.get("failed")),
                "publisher_ran": _int_value(publishers_payload.get("ran")),
                "publisher_updated": _int_value(publishers_payload.get("updated")),
                "mounts_refreshed": _int_value(mounts_payload.get("refreshed")),
            },
            visible=False,
        )
        payload = {
            "status": "ok",
            "home": compact_user_path(self.home.root),
            "tasks": {"materialized": len(tasks), "items": [task.id for task in tasks]},
            "task_notifications": task_notifications,
            "connectors": connector_payload,
            "watchers": watchers_payload,
            "blogs": blogs_payload,
            "radars": radars_payload,
            "automations": automations_payload,
            "publishers": publishers_payload,
            "mounts": mounts_payload,
            "okf": okf_payload,
            "health": {
                "status": health_payload.get("status"),
                "issue_count": len(health_payload.get("issues", [])),
                "action_count": len(health_payload.get("actions", [])),
            },
            "usage": usage_payload,
            "prune": prune_payload,
        }
        task_health = build_task_health_summary(payload)
        payload["task_health"] = task_health
        if notify_task_health:
            payload["task_health_notification"] = self.task_health_notifier.notify_once_per_day(
                task_health, tick_time=tick_time
            )
        return payload


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
