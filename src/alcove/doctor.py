from __future__ import annotations

import shutil

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
        return {
            "name": "workspace",
            "status": "ok" if self.paths.config.is_file() else "missing",
            "message": "Alcove workspace config",
            "path": str(self.paths.config),
        }

    def _path_check(self, name: str) -> dict:
        path = getattr(self.paths, name)
        return {
            "name": name,
            "status": "ok" if path.is_dir() else "missing",
            "message": f"{name} data directory",
            "path": str(path),
        }

    def _validation_check(self) -> dict:
        issues = ValidateModule(self.workspace).validate(strict_quality=False)
        return {
            "name": "validation",
            "status": "issues" if issues else "ok",
            "message": "Workspace validation",
            "count": len(issues),
        }

    def _command_check(self, command: str, message: str) -> dict:
        path = shutil.which(command)
        check = {
            "name": command,
            "status": "ok" if path else "missing",
            "message": message,
        }
        if path:
            check["path"] = path
        return check

    def _has_issues(self, checks: list[dict]) -> bool:
        return any(check["status"] in {"issues", "missing"} for check in checks)
