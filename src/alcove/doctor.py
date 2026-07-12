from __future__ import annotations

import shutil

from alcove.paths import compact_user_path
from alcove.validate import ValidateModule
from alcove.workspace import Workspace


class DoctorModule:
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.paths = workspace.paths()

    def check(self) -> dict:
        checks = [
            self._workspace_check(),
            self._command_check("uv", "Python project runner and installer"),
            self._command_check("alcove", "Installed Alcove CLI"),
        ]
        for name in ("knowledge", "inbox", "archive", "todo"):
            checks.append(self._path_check(name))
        checks.append(self._validation_check())
        return {
            "status": "issues" if self._has_issues(checks) else "ok",
            "workspace": str(self.workspace.root),
            "checks": checks,
        }

    def _workspace_check(self) -> dict:
        path = self.paths.config
        status = "ok" if path.is_file() else "missing"
        return {
            "name": "workspace",
            "component": "Workspace config",
            "status": status,
            "message": "Alcove workspace config",
            "remediation": "Run `alcove init` in this knowledge base."
            if status == "missing"
            else "",
            "path": compact_user_path(path),
        }

    def _path_check(self, name: str) -> dict:
        path = getattr(self.paths, name)
        status = "ok" if path.is_dir() else "missing"
        return {
            "name": name,
            "component": self._component_label(name),
            "status": status,
            "message": f"{name} data directory",
            "remediation": f"Create the {name} directory or rerun `alcove init`."
            if status == "missing"
            else "",
            "path": compact_user_path(path),
        }

    def _validation_check(self) -> dict:
        issues = ValidateModule(self.workspace).validate(strict_quality=False)
        status = "issues" if issues else "ok"
        return {
            "name": "validation",
            "component": "Knowledge validation",
            "status": status,
            "message": "Workspace validation",
            "remediation": "Run `alcove validate --json` and fix the listed OKF issues."
            if status == "issues"
            else "",
            "count": len(issues),
        }

    def _command_check(self, command: str, message: str) -> dict:
        path = shutil.which(command)
        status = "ok" if path else "missing"
        check = {
            "name": command,
            "component": self._component_label(command),
            "status": status,
            "message": message,
            "remediation": self._command_remediation(command) if status == "missing" else "",
        }
        if path:
            check["path"] = compact_user_path(path)
        return check

    def _has_issues(self, checks: list[dict]) -> bool:
        return any(check["status"] in {"issues", "missing"} for check in checks)

    def _component_label(self, name: str) -> str:
        return {
            "uv": "Python runner",
            "alcove": "Alcove CLI",
            "knowledge": "Managed knowledge",
            "inbox": "Capture inbox",
            "archive": "Archive storage",
            "todo": "Deferred inbox items",
        }.get(name, name.replace("-", " ").title())

    def _command_remediation(self, command: str) -> str:
        if command == "uv":
            return "Install uv and ensure it is available on PATH."
        if command == "alcove":
            return "Install Alcove in the active environment or run through `uv run alcove`."
        return f"Install {command} and ensure it is available on PATH."
