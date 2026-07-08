from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from alcove.gardener import GardenerModule
from alcove.inbox import InboxModule
from alcove.knowledge import KnowledgeModule, NoteSourceRequest
from alcove.mounts import MountsModule
from alcove.pins import AddPinRequest, PinsModule
from alcove.search import SearchModule, SearchRequest
from alcove.tasks import AddTaskRequest, TasksModule
from alcove.taxonomy import load_taxonomy, split_domain_topic
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


def note_source_tool(
    workspace: str,
    platform: str,
    title: str,
    topic: str,
    resource: str = "",
    summary: str = "",
    tags: list[str] | None = None,
    published_date: str | None = None,
    create_concept: bool = True,
) -> dict:
    """Record a source note in Alcove knowledge."""
    alcove = Workspace.discover(Path(workspace))
    result = KnowledgeModule(alcove).note_source(
        NoteSourceRequest(
            platform=platform,
            title=title,
            topic=topic,
            resource=resource,
            summary=summary,
            tags=tags or [],
            published_date=published_date,
            create_concept=create_concept,
        )
    )
    return {
        "workspace": str(alcove.root),
        "status": "noted",
        "source_path": str(result.source_path),
        "concept_path": str(result.concept_path) if result.concept_path else "",
    }


def get_topic_tool(workspace: str, topic: str, limit: int = 20) -> dict:
    """Return a topic overview and active Alcove docs for that topic."""
    alcove = Workspace.discover(Path(workspace))
    taxonomy = load_taxonomy(alcove.paths().knowledge)
    domain, topic_slug = split_domain_topic(topic, taxonomy)
    rows = SearchModule(alcove).search(
        SearchRequest(topic=f"{domain}/{topic_slug}", status="active", limit=limit)
    )
    return {
        "workspace": str(alcove.root),
        "domain": domain,
        "topic": topic_slug,
        "count": len(rows),
        "results": rows,
    }


def pin_add_tool(
    workspace: str,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    priority: str = "medium",
    source_refs: list[str] | None = None,
) -> dict:
    """Create a pinned personal note."""
    alcove = Workspace.discover(Path(workspace))
    result = PinsModule(alcove).add(
        AddPinRequest(
            title=title,
            description=description,
            tags=tags or [],
            priority=priority,
            source_refs=source_refs or [],
        )
    )
    return {
        "workspace": str(alcove.root),
        "status": "pinned",
        "path": str(result.path),
        "pin": _pin_dict(result.pin),
    }


def task_add_tool(
    workspace: str,
    title: str,
    notes: str = "",
    tags: list[str] | None = None,
    priority: str = "medium",
    due: str = "",
) -> dict:
    """Create a personal task."""
    alcove = Workspace.discover(Path(workspace))
    task = TasksModule(alcove).task_add(
        AddTaskRequest(
            title=title,
            notes=notes,
            tags=tags or [],
            priority=priority,
            due=due,
        )
    )
    return {
        "workspace": str(alcove.root),
        "status": "added",
        "task": asdict(task),
    }


def task_list_tool(workspace: str, status: str = "pending") -> dict:
    """List personal tasks."""
    alcove = Workspace.discover(Path(workspace))
    tasks = [asdict(task) for task in TasksModule(alcove).task_list(status)]
    return {
        "workspace": str(alcove.root),
        "count": len(tasks),
        "tasks": tasks,
    }


def gardener_tool(workspace: str, prune: bool = False) -> dict:
    """Scan Alcove knowledge health and optionally prune safe issues."""
    alcove = Workspace.discover(Path(workspace))
    report = GardenerModule(alcove).gardener(prune=prune)
    return {
        "workspace": str(alcove.root),
        "issues": report.issues,
        "actions": report.actions,
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

    @mcp.tool
    def alcove_note_source(
        platform: str,
        title: str,
        topic: str,
        workspace: str = "",
        resource: str = "",
        summary: str = "",
        tags: list[str] | None = None,
        published_date: str | None = None,
        create_concept: bool = True,
    ) -> dict:
        """Record a source note in Alcove knowledge."""
        return note_source_tool(
            workspace or _default_workspace(default_workspace),
            platform=platform,
            title=title,
            topic=topic,
            resource=resource,
            summary=summary,
            tags=tags,
            published_date=published_date,
            create_concept=create_concept,
        )

    @mcp.tool
    def alcove_get_topic(
        topic: str,
        workspace: str = "",
        limit: int = 20,
    ) -> dict:
        """Return a topic overview and active Alcove docs for that topic."""
        return get_topic_tool(
            workspace or _default_workspace(default_workspace),
            topic=topic,
            limit=limit,
        )

    @mcp.tool
    def alcove_pin_add(
        title: str,
        workspace: str = "",
        description: str = "",
        tags: list[str] | None = None,
        priority: str = "medium",
        source_refs: list[str] | None = None,
    ) -> dict:
        """Create a pinned personal note."""
        return pin_add_tool(
            workspace or _default_workspace(default_workspace),
            title=title,
            description=description,
            tags=tags,
            priority=priority,
            source_refs=source_refs,
        )

    @mcp.tool
    def alcove_task_add(
        title: str,
        workspace: str = "",
        notes: str = "",
        tags: list[str] | None = None,
        priority: str = "medium",
        due: str = "",
    ) -> dict:
        """Create a personal task."""
        return task_add_tool(
            workspace or _default_workspace(default_workspace),
            title=title,
            notes=notes,
            tags=tags,
            priority=priority,
            due=due,
        )

    @mcp.tool
    def alcove_task_list(workspace: str = "", status: str = "pending") -> dict:
        """List personal tasks."""
        return task_list_tool(
            workspace or _default_workspace(default_workspace),
            status=status,
        )

    @mcp.tool
    def alcove_gardener(workspace: str = "", prune: bool = False) -> dict:
        """Scan Alcove knowledge health and optionally prune safe issues."""
        return gardener_tool(
            workspace or _default_workspace(default_workspace),
            prune=prune,
        )

    return mcp


def run_mcp_server(default_workspace: str | None = None) -> None:
    create_mcp_server(default_workspace).run()


def _default_workspace(default_workspace: str | None) -> str:
    return default_workspace or "."


def _pin_dict(pin) -> dict:
    return {
        "id": pin.id,
        "title": pin.title,
        "description": pin.description,
        "tags": pin.tags,
        "status": pin.status,
        "priority": pin.priority,
        "source_refs": pin.source_refs,
        "path": str(pin.path),
    }
