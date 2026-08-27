from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
from typing import Any

from alcove.home import AlcoveHome
from alcove.paths import compact_user_path


SERVICE_DOMAIN = "com.octopusgarage.alcove"


@dataclass(frozen=True)
class ServiceTarget:
    name: str
    label: str
    plist_path: Path


class ServiceLaunchd:
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
                self._launchctl("bootstrap", target, allow_failure=True)
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
        paths = [
            str(Path.home() / ".local" / "bin"),
            str(Path.home() / ".cargo" / "bin"),
            *_current_executable_dirs("alcove", "codex", "claude", "node"),
            *_nvm_bin_dirs(),
            *_path_entries(os.environ.get("PATH", "")),
            "/opt/homebrew/bin",
            "/usr/local/bin",
            "/usr/bin",
            "/bin",
            "/usr/sbin",
            "/sbin",
        ]
        return ":".join(_dedupe_paths(paths))

    def _write_plist(self, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise RuntimeError(
                f"Refusing to write launchd plist through symlink: {compact_user_path(path)}"
            )
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


def _current_executable_dirs(*commands: str) -> list[str]:
    paths: list[str] = []
    for command in commands:
        executable = shutil.which(command)
        if executable:
            paths.append(str(Path(executable).resolve().parent))
    return paths


def _nvm_bin_dirs() -> list[str]:
    root = Path.home() / ".nvm" / "versions" / "node"
    if not root.is_dir():
        return []
    return [str(path) for path in sorted(root.glob("*/bin"), reverse=True) if path.is_dir()]


def _path_entries(value: str) -> list[str]:
    return [entry for entry in value.split(":") if entry]


def _dedupe_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for path in paths:
        expanded = str(Path(path).expanduser())
        if expanded in seen:
            continue
        seen.add(expanded)
        result.append(expanded)
    return result
