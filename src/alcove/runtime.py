from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alcove.home import AlcoveHome
from alcove.paths import compact_user_path
from alcove.workspace import Workspace
from alcove.errors import WorkspaceNotFoundError


@dataclass(frozen=True)
class AlcoveRuntime:
    workspace: Workspace | None = None
    home: AlcoveHome | None = None

    @classmethod
    def resolve(
        cls,
        workspace: Workspace | Path | str | None = None,
        home: AlcoveHome | Path | str | None = None,
        kb: str | None = None,
        require_workspace: bool = False,
        init_default_home: bool = True,
    ) -> "AlcoveRuntime":
        alcove_workspace = cls._resolve_workspace(workspace)
        if alcove_workspace is None and require_workspace and not kb:
            alcove_workspace = cls._discover_current_workspace()
        alcove_home = cls._resolve_home(
            home,
            init_default=bool(kb)
            or (init_default_home and alcove_workspace is None and home is None),
        )
        if kb:
            if alcove_home is None:
                alcove_home = AlcoveHome.init()
            alcove_workspace = Workspace.discover(alcove_home.get_knowledge_base(kb).path)
        if require_workspace and alcove_workspace is None:
            raise ValueError("An Alcove workspace is required")
        if alcove_home is None and alcove_workspace is None and init_default_home:
            alcove_home = AlcoveHome.init()
        return cls(workspace=alcove_workspace, home=alcove_home)

    @classmethod
    def from_modules(
        cls,
        workspace: Workspace | None = None,
        home: AlcoveHome | None = None,
        default_to_home: bool = True,
    ) -> "AlcoveRuntime":
        if home is None and workspace is None and default_to_home:
            home = AlcoveHome.init()
        return cls(workspace=workspace, home=home)

    @staticmethod
    def _resolve_home(
        home: AlcoveHome | Path | str | None,
        init_default: bool,
    ) -> AlcoveHome | None:
        if isinstance(home, AlcoveHome):
            return home
        if home:
            return AlcoveHome.init(Path(home))
        if init_default:
            return AlcoveHome.init()
        return None

    @staticmethod
    def _resolve_workspace(workspace: Workspace | Path | str | None) -> Workspace | None:
        if isinstance(workspace, Workspace):
            return workspace
        if workspace:
            return Workspace.discover(Path(workspace))
        return None

    @staticmethod
    def _discover_current_workspace() -> Workspace | None:
        try:
            return Workspace.discover()
        except WorkspaceNotFoundError:
            return None

    @property
    def is_global(self) -> bool:
        return self.home is not None

    @property
    def knowledge_root(self) -> Path | None:
        return self.workspace.paths().knowledge if self.workspace is not None else None

    def require_workspace(self) -> Workspace:
        if self.workspace is None:
            raise ValueError("An Alcove workspace is required")
        return self.workspace

    @property
    def pins_root(self) -> Path:
        if self.home is not None:
            return self.home.paths().pins
        if self.workspace is None:
            raise ValueError("Pins root requires home or workspace")
        return self.workspace.paths().pins

    @property
    def projects_root(self) -> Path:
        if self.home is not None:
            return self.home.paths().projects
        if self.workspace is None:
            raise ValueError("Projects root requires home or workspace")
        return self.workspace.root / "projects"

    @property
    def prompts_root(self) -> Path:
        if self.home is not None:
            return self.home.paths().prompts
        if self.workspace is None:
            raise ValueError("Prompts root requires home or workspace")
        return self.workspace.root / "prompts"

    @property
    def tasks_root(self) -> Path:
        if self.home is not None:
            return self.home.paths().tasks
        if self.workspace is None:
            raise ValueError("Tasks root requires home or workspace")
        return self.workspace.paths().tasks

    @property
    def mounts_root(self) -> Path:
        if self.home is not None:
            return self.home.paths().mounts
        if self.workspace is None:
            raise ValueError("Mounts root requires home or workspace")
        return self.workspace.paths().mounts

    @property
    def mount_indexes_root(self) -> Path:
        if self.home is not None:
            return self.home.paths().mount_indexes
        return self.mounts_root

    @property
    def connectors_root(self) -> Path:
        if self.home is not None:
            return self.home.paths().connectors
        if self.workspace is None:
            raise ValueError("Connectors root requires home or workspace")
        return self.workspace.paths().state / "connectors"

    @property
    def taxonomy_root(self) -> Path:
        if self.knowledge_root is not None:
            return self.knowledge_root
        if self.home is not None:
            return self.home.paths().root
        raise ValueError("Taxonomy root requires home or workspace")

    def scope_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        scoped = dict(payload)
        if self.workspace is not None:
            scoped["workspace"] = compact_user_path(self.workspace.root)
        if self.home is not None:
            scoped["home"] = compact_user_path(self.home.root)
        return scoped
