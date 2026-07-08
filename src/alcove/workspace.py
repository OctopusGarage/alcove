from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from alcove.errors import (
    WorkspaceConfigError,
    WorkspaceInitializationError,
    WorkspaceNotFoundError,
)


WORKSPACE_DIR = ".alcove"
CONFIG_FILE = "config.yml"
DATA_DIRS = ("knowledge", "inbox", "archive", "todo")
LEGACY_DATA_DIRS = ("pins", "tasks", "mounts")


@dataclass(frozen=True)
class WorkspacePaths:
    root: Path
    state: Path
    config: Path
    knowledge: Path
    inbox: Path
    archive: Path
    pins: Path
    tasks: Path
    mounts: Path
    todo: Path
    index: Path
    logs: Path


@dataclass(frozen=True)
class Workspace:
    root: Path

    @classmethod
    def init(cls, root: Path | str) -> "Workspace":
        root_path = Path(root).expanduser()
        try:
            root_path = root_path.resolve()
            root_path.mkdir(parents=True, exist_ok=True)
            state = root_path / WORKSPACE_DIR
            state.mkdir(exist_ok=True)
            (state / "connectors").mkdir(exist_ok=True)
            (state / "logs").mkdir(exist_ok=True)
            for name in DATA_DIRS:
                (root_path / name).mkdir(exist_ok=True)
            config_path = state / CONFIG_FILE
            if not config_path.exists():
                config = {
                    "version": 1,
                    "kind": "managed-kb",
                    "paths": {name: name for name in DATA_DIRS},
                }
                config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        except OSError as exc:
            raise WorkspaceInitializationError(
                f"Could not initialize Alcove workspace at {root_path}: {exc}"
            ) from exc
        return cls(root_path)

    @classmethod
    def discover(cls, start: Path | str | None = None) -> "Workspace":
        current = Path(start or Path.cwd()).expanduser().resolve()
        if current.is_file():
            current = current.parent
        while True:
            if (current / WORKSPACE_DIR / CONFIG_FILE).is_file():
                return cls(current)
            if current.parent == current:
                raise WorkspaceNotFoundError("No Alcove workspace found. Run `alcove init`.")
            current = current.parent

    def paths(self) -> WorkspacePaths:
        state = self.root / WORKSPACE_DIR
        configured_paths = self._configured_data_paths()
        return WorkspacePaths(
            root=self.root,
            state=state,
            config=state / CONFIG_FILE,
            knowledge=self._resolve_data_path("knowledge", configured_paths),
            inbox=self._resolve_data_path("inbox", configured_paths),
            archive=self._resolve_data_path("archive", configured_paths),
            pins=self._resolve_data_path("pins", configured_paths),
            tasks=self._resolve_data_path("tasks", configured_paths),
            mounts=self._resolve_data_path("mounts", configured_paths),
            todo=self._resolve_data_path("todo", configured_paths),
            index=state / "index.sqlite",
            logs=state / "logs",
        )

    def load_config(self) -> dict[str, Any]:
        path = self.root / WORKSPACE_DIR / CONFIG_FILE
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise WorkspaceConfigError(f"Could not parse Alcove config at {path}: {exc}") from exc

    def _configured_data_paths(self) -> dict[str, str]:
        paths = self.load_config().get("paths", {})
        if not isinstance(paths, dict):
            return {}
        return {str(name): str(path) for name, path in paths.items()}

    def _resolve_data_path(self, name: str, configured_paths: dict[str, str]) -> Path:
        configured_path = Path(configured_paths.get(name, name)).expanduser()
        if configured_path.is_absolute():
            return configured_path
        return self.root / configured_path

    def status(self) -> dict[str, Any]:
        paths = self.paths()
        return {
            "initialized": paths.config.is_file(),
            "root": str(self.root),
            "paths": {
                "knowledge": str(paths.knowledge),
                "inbox": str(paths.inbox),
                "archive": str(paths.archive),
                "todo": str(paths.todo),
            },
        }
