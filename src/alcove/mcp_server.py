from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from alcove.inbox import InboxModule
from alcove.mounts import MountsModule
from alcove.search import SearchModule, SearchRequest
from alcove.workspace import Workspace


def search_tool(
    workspace: str,
    query: str = "",
    type_filter: str | None = None,
    tag: str | None = None,
    topic: str | None = None,
    platform: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    min_confidence: float | None = None,
    status: str | None = None,
    limit: int = 20,
) -> dict:
    """Search Alcove knowledge, pins, ideas, and tasks."""
    alcove = Workspace.discover(Path(workspace))
    results = SearchModule(alcove).search(
        SearchRequest(
            query=query,
            type_filter=type_filter,
            tag=tag,
            topic=topic,
            platform=platform,
            date_from=date_from,
            date_to=date_to,
            min_confidence=min_confidence,
            status=status,
            limit=limit,
        )
    )
    return {
        "workspace": str(alcove.root),
        "count": len(results),
        "results": results,
    }


def inbox_peek_tool(workspace: str) -> dict:
    """Inspect the oldest pending Alcove inbox item."""
    alcove = Workspace.discover(Path(workspace))
    item = InboxModule(alcove).peek()
    return {
        "workspace": str(alcove.root),
        "item": asdict(item) if item is not None else None,
    }


def mount_list_tool(workspace: str, status: str = "active") -> dict:
    """List configured Alcove mounts."""
    alcove = Workspace.discover(Path(workspace))
    mounts = [asdict(mount) for mount in MountsModule(alcove).list(status)]
    return {
        "workspace": str(alcove.root),
        "count": len(mounts),
        "mounts": mounts,
    }


def create_mcp_server(default_workspace: str | None = None):
    from fastmcp import FastMCP

    mcp = FastMCP("alcove")

    @mcp.tool
    def alcove_search(
        query: str = "",
        workspace: str = "",
        type_filter: str | None = None,
        tag: str | None = None,
        topic: str | None = None,
        platform: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        min_confidence: float | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> dict:
        """Search Alcove knowledge, pins, ideas, and tasks."""
        return search_tool(
            workspace or _default_workspace(default_workspace),
            query=query,
            type_filter=type_filter,
            tag=tag,
            topic=topic,
            platform=platform,
            date_from=date_from,
            date_to=date_to,
            min_confidence=min_confidence,
            status=status,
            limit=limit,
        )

    @mcp.tool
    def alcove_inbox_peek(workspace: str = "") -> dict:
        """Inspect the oldest pending Alcove inbox item."""
        return inbox_peek_tool(workspace or _default_workspace(default_workspace))

    @mcp.tool
    def alcove_mount_list(workspace: str = "", status: str = "active") -> dict:
        """List configured Alcove mounts."""
        return mount_list_tool(
            workspace or _default_workspace(default_workspace),
            status=status,
        )

    return mcp


def run_mcp_server(default_workspace: str | None = None) -> None:
    create_mcp_server(default_workspace).run()


def _default_workspace(default_workspace: str | None) -> str:
    return default_workspace or "."
