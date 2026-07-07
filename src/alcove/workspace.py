from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from alcove.errors import WorkspaceNotFoundError


WORKSPACE_DIR = ".alcove"
CONFIG_FILE = "config.yml"
DATA_DIRS = ("knowledge", "inbox", "archive", "pins", "tasks", "mounts", "todo")


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
        root_path = Path(root).expanduser().resolve()
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
                "workspace": {"name": root_path.name},
                "paths": {name: name for name in DATA_DIRS},
            }
            config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
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
        return WorkspacePaths(
            root=self.root,
            state=state,
            config=state / CONFIG_FILE,
            knowledge=self.root / "knowledge",
            inbox=self.root / "inbox",
            archive=self.root / "archive",
            pins=self.root / "pins",
            tasks=self.root / "tasks",
            mounts=self.root / "mounts",
            todo=self.root / "todo",
            index=state / "index.sqlite",
            logs=state / "logs",
        )

    def load_config(self) -> dict[str, Any]:
        path = self.paths().config
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def status(self) -> dict[str, Any]:
        paths = self.paths()
        return {
            "initialized": paths.config.is_file(),
            "root": str(self.root),
            "paths": {
                "knowledge": str(paths.knowledge),
                "inbox": str(paths.inbox),
                "archive": str(paths.archive),
                "pins": str(paths.pins),
                "tasks": str(paths.tasks),
                "mounts": str(paths.mounts),
                "todo": str(paths.todo),
            },
        }
