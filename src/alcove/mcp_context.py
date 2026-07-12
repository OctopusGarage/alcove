from __future__ import annotations

from pathlib import Path
from typing import Any

from alcove.application import AlcoveApplication
from alcove.runtime import AlcoveRuntime


def agent_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    for key in ("workspace", "home"):
        public.pop(key, None)
    return public


class McpInvocationContext:
    """Resolve MCP workspace/home defaults before crossing the application seam."""

    def __init__(
        self,
        default_workspace: str | None = None,
        default_home: str | None = None,
    ) -> None:
        self.default_workspace = default_workspace
        self.default_home = default_home

    def app(self, workspace: str = "", home: str = "") -> AlcoveApplication:
        return AlcoveApplication(_runtime(workspace, home))

    def scoped_app(self, workspace: str = "", home: str = "") -> AlcoveApplication:
        effective_home = self.effective_home(home)
        return self.app(
            self.effective_workspace(workspace, home=effective_home),
            effective_home,
        )

    def managed_app(self, workspace: str = "") -> AlcoveApplication:
        return self.app(workspace or self.default_workspace or ".", "")

    def effective_home(self, home: str = "") -> str:
        return home or self.default_home or ""

    def effective_workspace(self, workspace: str = "", home: str = "") -> str:
        if workspace:
            return workspace
        if self.default_workspace:
            return self.default_workspace
        if home:
            return ""
        return "."


def _runtime(workspace: str = "", home: str = "") -> AlcoveRuntime:
    return AlcoveRuntime.resolve(
        workspace=Path(workspace) if workspace else None,
        home=Path(home) if home else None,
        init_default_home=True,
    )
