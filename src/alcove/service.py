from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import plistlib
import subprocess
import sys
from typing import Any

from alcove.application import AlcoveApplication
from alcove.automations import AutomationsModule
from alcove.blog_monitor import BlogMonitorModule
from alcove.dashboard import DashboardModule
from alcove.home import AlcoveHome
from alcove.paths import compact_user_path
from alcove.publishers import PublisherModule
from alcove.radars import RadarModule
from alcove.runtime import AlcoveRuntime
from alcove.tasks import TasksModule
from alcove.usage import UsageRecorder
from alcove.watchers import WatcherModule


SERVICE_DOMAIN = "com.octopusgarage.alcove"


@dataclass(frozen=True)
class ServiceTarget:
    name: str
    label: str
    plist_path: Path


class ServiceModule:
    def __init__(self, home: AlcoveHome) -> None:
        self.home = home
        self.launch_agents = Path.home() / "Library" / "LaunchAgents"
        self.logs = self.home.paths().logs / "service"

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
        targets = self._selected_targets(dashboard=dashboard, scheduler=scheduler)
        files = []
        for target in targets:
            payload = (
                self._dashboard_plist(target, host=host, port=port)
                if target.name == "dashboard"
                else self._scheduler_plist(target, interval_minutes=interval_minutes)
            )
            files.append(self._write_plist(target.plist_path, payload))
            if load:
                self._launchctl("bootstrap", target)
                self._launchctl("kickstart", target)
        return self._payload("installed", targets, files)

    def uninstall(
        self, *, dashboard: bool, scheduler: bool, unload: bool = False
    ) -> dict[str, Any]:
        targets = self._selected_targets(dashboard=dashboard, scheduler=scheduler)
        files = []
        for target in targets:
            if unload:
                self._launchctl("bootout", target, allow_failure=True)
            action = "removed" if target.plist_path.exists() else "not_found"
            if target.plist_path.exists():
                target.plist_path.unlink()
            files.append(
                {
                    "name": target.name,
                    "path": compact_user_path(target.plist_path),
                    "action": action,
                }
            )
        return self._payload("uninstalled", targets, files)

    def status(self, *, dashboard: bool, scheduler: bool) -> dict[str, Any]:
        targets = self._selected_targets(dashboard=dashboard, scheduler=scheduler)
        files = []
        for target in targets:
            files.append(
                {
                    "name": target.name,
                    "label": target.label,
                    "path": compact_user_path(target.plist_path),
                    "installed": target.plist_path.is_file(),
                    "loaded": self._is_loaded(target),
                }
            )
        return self._payload("status", targets, files)

    def start(self, *, dashboard: bool, scheduler: bool) -> dict[str, Any]:
        targets = self._selected_targets(dashboard=dashboard, scheduler=scheduler)
        actions = []
        for target in targets:
            self._launchctl("bootstrap", target, allow_failure=True)
            self._launchctl("kickstart", target)
            actions.append({"name": target.name, "action": "started"})
        return self._payload("started", targets, actions)

    def stop(self, *, dashboard: bool, scheduler: bool) -> dict[str, Any]:
        targets = self._selected_targets(dashboard=dashboard, scheduler=scheduler)
        actions = []
        for target in targets:
            self._launchctl("bootout", target, allow_failure=True)
            actions.append({"name": target.name, "action": "stopped"})
        return self._payload("stopped", targets, actions)

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
        fix_health: bool = True,
        today: str = "",
    ) -> dict[str, Any]:
        runtime = AlcoveRuntime.from_modules(home=self.home)
        app = AlcoveApplication(runtime)
        usage = UsageRecorder(self.home)
        task_module = TasksModule(home=self.home)
        tasks = task_module.routine_materialize_due(today=today or None)
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
            },
            visible=False,
        )
        return {
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
            "okf": okf_payload,
            "health": {
                "status": health_payload.get("status"),
                "issue_count": len(health_payload.get("issues", [])),
                "action_count": len(health_payload.get("actions", [])),
            },
            "usage": usage_payload,
            "prune": prune_payload,
        }

    def _selected_targets(self, *, dashboard: bool, scheduler: bool) -> list[ServiceTarget]:
        if not dashboard and not scheduler:
            dashboard = True
            scheduler = True
        targets = []
        if dashboard:
            targets.append(self._target("dashboard"))
        if scheduler:
            targets.append(self._target("scheduler"))
        return targets

    def _target(self, name: str) -> ServiceTarget:
        label = f"{SERVICE_DOMAIN}.{name}"
        return ServiceTarget(
            name=name, label=label, plist_path=self.launch_agents / f"{label}.plist"
        )

    def _dashboard_plist(self, target: ServiceTarget, *, host: str, port: int) -> dict[str, Any]:
        return self._plist(
            target,
            command=[
                "alcove",
                "serve",
                "--dashboard",
                "--home",
                compact_user_path(self.home.root),
                "--host",
                host,
                "--port",
                str(port),
            ],
            run_at_load=True,
            keep_alive=True,
        )

    def _scheduler_plist(self, target: ServiceTarget, *, interval_minutes: int) -> dict[str, Any]:
        return self._plist(
            target,
            command=[
                "alcove",
                "service",
                "tick",
                "--home",
                compact_user_path(self.home.root),
                "--json",
            ],
            run_at_load=True,
            keep_alive=False,
            start_interval=max(interval_minutes, 1) * 60,
        )

    def _plist(
        self,
        target: ServiceTarget,
        *,
        command: list[str],
        run_at_load: bool,
        keep_alive: bool,
        start_interval: int | None = None,
    ) -> dict[str, Any]:
        self.logs.mkdir(parents=True, exist_ok=True)
        shell_command = " ".join(_shell_quote(part) for part in command)
        payload: dict[str, Any] = {
            "Label": target.label,
            "ProgramArguments": ["/bin/zsh", "-lc", f"exec {shell_command}"],
            "RunAtLoad": run_at_load,
            "KeepAlive": keep_alive,
            "StandardOutPath": str(self.logs / f"{target.name}.out.log"),
            "StandardErrorPath": str(self.logs / f"{target.name}.err.log"),
            "EnvironmentVariables": {
                "PATH": self._launchd_path(),
            },
        }
        if start_interval is not None:
            payload["StartInterval"] = start_interval
        return payload

    def _launchd_path(self) -> str:
        return ":".join(
            [
                str(Path.home() / ".local" / "bin"),
                str(Path.home() / ".cargo" / "bin"),
                "/opt/homebrew/bin",
                "/usr/local/bin",
                "/usr/bin",
                "/bin",
                "/usr/sbin",
                "/sbin",
            ]
        )

    def _write_plist(self, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
        path.parent.mkdir(parents=True, exist_ok=True)
        before = path.read_bytes() if path.is_file() else b""
        content = plistlib.dumps(payload, sort_keys=False)
        action = "created" if not before else "unchanged" if before == content else "updated"
        if before != content:
            path.write_bytes(content)
        return {"path": compact_user_path(path), "action": action, "label": payload["Label"]}

    def _launchctl(
        self, action: str, target: ServiceTarget, *, allow_failure: bool = False
    ) -> subprocess.CompletedProcess[str]:
        if sys.platform != "darwin":
            raise RuntimeError("launchd service management is only available on macOS")
        domain = f"gui/{os.getuid()}"
        if action == "bootstrap":
            cmd = ["/bin/launchctl", "bootstrap", domain, str(target.plist_path)]
        elif action == "bootout":
            cmd = ["/bin/launchctl", "bootout", domain, str(target.plist_path)]
        elif action == "kickstart":
            cmd = ["/bin/launchctl", "kickstart", "-k", f"{domain}/{target.label}"]
        else:
            raise ValueError(f"Unknown launchctl action: {action}")
        result = subprocess.run(cmd, text=True, capture_output=True, check=False)  # noqa: S603
        if result.returncode != 0 and not allow_failure:
            raise RuntimeError(result.stderr.strip() or f"launchctl {action} failed")
        return result

    def _is_loaded(self, target: ServiceTarget) -> bool:
        if sys.platform != "darwin":
            return False
        domain = f"gui/{os.getuid()}/{target.label}"
        result = subprocess.run(  # noqa: S603
            ["/bin/launchctl", "print", domain],
            text=True,
            capture_output=True,
            check=False,
        )
        return result.returncode == 0

    def _payload(
        self, status: str, targets: list[ServiceTarget], records: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return {
            "status": status,
            "home": compact_user_path(self.home.root),
            "targets": [target.name for target in targets],
            "records": records,
        }


def _shell_quote(value: str) -> str:
    if not value:
        return "''"
    safe = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_+-=.,/:@%")
    if all(char in safe for char in value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
