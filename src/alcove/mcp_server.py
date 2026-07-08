from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from alcove.gardener import GardenerModule
from alcove.home import AlcoveHome
from alcove.inbox import InboxModule
from alcove.knowledge import KnowledgeModule, NoteSourceRequest
from alcove.linking import LinkSourceRequest, LinkingModule
from alcove.mounts import MountsModule
from alcove.pins import AddPinRequest, PinsModule
from alcove.search import SearchModule, SearchRequest
from alcove.tasks import AddRoutineRequest, AddTaskRequest, TasksModule
from alcove.taxonomy import load_taxonomy, split_domain_topic
from alcove.workspace import Workspace


def search_tool(
    workspace: str = "",
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
    home: str = "",
) -> dict:
    """Search Alcove knowledge, pins, ideas, and tasks."""
    alcove, alcove_home = _workspace_home(workspace, home)
    results = SearchModule(alcove, home=alcove_home).search(
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
    payload = {
        "count": len(results),
        "results": results,
    }
    return _scope_payload(payload, alcove, alcove_home)


def inbox_peek_tool(workspace: str) -> dict:
    """Inspect the oldest pending Alcove inbox item."""
    alcove = Workspace.discover(Path(workspace))
    item = InboxModule(alcove).peek()
    return {
        "workspace": str(alcove.root),
        "item": asdict(item) if item is not None else None,
    }


def mount_list_tool(workspace: str = "", status: str = "active", home: str = "") -> dict:
    """List configured Alcove mounts."""
    alcove, alcove_home = _workspace_home(workspace, home)
    mounts = [asdict(mount) for mount in MountsModule(alcove, home=alcove_home).list(status)]
    payload = {
        "count": len(mounts),
        "mounts": mounts,
    }
    return _scope_payload(payload, alcove, alcove_home)


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
    home: str = "",
) -> dict:
    """Create a pinned personal note."""
    alcove, alcove_home = _workspace_home(workspace, home)
    result = PinsModule(alcove, home=alcove_home).add(
        AddPinRequest(
            title=title,
            description=description,
            tags=tags or [],
            priority=priority,
            source_refs=source_refs or [],
        )
    )
    payload = {
        "status": "pinned",
        "path": str(result.path),
        "pin": _pin_dict(result.pin),
    }
    return _scope_payload(payload, alcove, alcove_home)


def task_add_tool(
    workspace: str,
    title: str,
    notes: str = "",
    tags: list[str] | None = None,
    priority: str = "medium",
    due: str = "",
    home: str = "",
) -> dict:
    """Create a personal task."""
    alcove, alcove_home = _workspace_home(workspace, home)
    task = TasksModule(alcove, home=alcove_home).task_add(
        AddTaskRequest(
            title=title,
            notes=notes,
            tags=tags or [],
            priority=priority,
            due=due,
        )
    )
    payload = {
        "status": "added",
        "task": asdict(task),
    }
    return _scope_payload(payload, alcove, alcove_home)


def task_list_tool(workspace: str = "", status: str = "pending", home: str = "") -> dict:
    """List personal tasks."""
    alcove, alcove_home = _workspace_home(workspace, home)
    tasks = [asdict(task) for task in TasksModule(alcove, home=alcove_home).task_list(status)]
    payload = {
        "count": len(tasks),
        "tasks": tasks,
    }
    return _scope_payload(payload, alcove, alcove_home)


def idea_promote_tool(
    workspace: str,
    idea_id: str,
    priority: str = "medium",
    due: str = "",
    notes: str = "",
    home: str = "",
) -> dict:
    """Promote an idea into a concrete task."""
    alcove, alcove_home = _workspace_home(workspace, home)
    tasks = TasksModule(alcove, home=alcove_home)
    task = tasks.idea_promote_to_task(
        idea_id,
        priority=priority,
        due=due,
        notes=notes,
    )
    idea = next(
        item for item in tasks.idea_list(status="promoted") if item.promoted_task_id == task.id
    )
    payload = {
        "status": "promoted",
        "idea": asdict(idea),
        "task": asdict(task),
    }
    return _scope_payload(payload, alcove, alcove_home)


def routine_add_tool(
    workspace: str,
    title: str,
    notes: str = "",
    tags: list[str] | None = None,
    priority: str = "medium",
    every_days: int = 1,
    next_due: str = "",
    home: str = "",
) -> dict:
    """Create a recurring task template."""
    alcove, alcove_home = _workspace_home(workspace, home)
    routine = TasksModule(alcove, home=alcove_home).routine_add(
        AddRoutineRequest(
            title=title,
            notes=notes,
            tags=tags or [],
            priority=priority,
            every_days=every_days,
            next_due=next_due,
        )
    )
    payload = {
        "status": "added",
        "routine": asdict(routine),
    }
    return _scope_payload(payload, alcove, alcove_home)


def routine_list_tool(
    workspace: str = "",
    status: str = "active",
    home: str = "",
) -> dict:
    """List recurring task templates."""
    alcove, alcove_home = _workspace_home(workspace, home)
    routines = [
        asdict(routine) for routine in TasksModule(alcove, home=alcove_home).routine_list(status)
    ]
    payload = {
        "count": len(routines),
        "routines": routines,
    }
    return _scope_payload(payload, alcove, alcove_home)


def routine_materialize_due_tool(
    workspace: str = "",
    today: str = "",
    home: str = "",
) -> dict:
    """Create tasks for due recurring templates."""
    alcove, alcove_home = _workspace_home(workspace, home)
    created = TasksModule(alcove, home=alcove_home).routine_materialize_due(today=today or None)
    payload = {
        "status": "materialized",
        "created": [asdict(task) for task in created],
    }
    return _scope_payload(payload, alcove, alcove_home)


def link_source_tool(
    workspace: str,
    item_path: str,
    topic: str,
    summary: str = "",
    create_concept: bool = False,
) -> dict:
    """Create a Source from an indexed external item."""
    alcove = Workspace.discover(Path(workspace))
    return LinkingModule(alcove).link_source(
        LinkSourceRequest(
            item_path=item_path,
            topic=topic,
            summary=summary,
            create_concept=create_concept,
        )
    )


def gardener_tool(workspace: str, prune: bool = False) -> dict:
    """Scan Alcove knowledge health and optionally prune safe issues."""
    alcove = Workspace.discover(Path(workspace))
    report = GardenerModule(alcove).gardener(prune=prune)
    return {
        "workspace": str(alcove.root),
        "issues": report.issues,
        "actions": report.actions,
    }


def create_mcp_server(
    default_workspace: str | None = None,
    default_home: str | None = None,
):
    from fastmcp import FastMCP

    mcp = FastMCP("alcove")

    @mcp.tool
    def alcove_search(
        query: str = "",
        workspace: str = "",
        home: str = "",
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
        effective_home = _effective_home(home, default_home)
        return search_tool(
            _effective_workspace(workspace, default_workspace, effective_home),
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
            home=effective_home,
        )

    @mcp.tool
    def alcove_inbox_peek(workspace: str = "") -> dict:
        """Inspect the oldest pending Alcove inbox item."""
        return inbox_peek_tool(workspace or _default_workspace(default_workspace))

    @mcp.tool
    def alcove_mount_list(
        workspace: str = "",
        status: str = "active",
        home: str = "",
    ) -> dict:
        """List configured Alcove mounts."""
        effective_home = _effective_home(home, default_home)
        return mount_list_tool(
            _effective_workspace(workspace, default_workspace, effective_home),
            status=status,
            home=effective_home,
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
        home: str = "",
        description: str = "",
        tags: list[str] | None = None,
        priority: str = "medium",
        source_refs: list[str] | None = None,
    ) -> dict:
        """Create a pinned personal note."""
        effective_home = _effective_home(home, default_home)
        return pin_add_tool(
            _effective_workspace(workspace, default_workspace, effective_home),
            title=title,
            description=description,
            tags=tags,
            priority=priority,
            source_refs=source_refs,
            home=effective_home,
        )

    @mcp.tool
    def alcove_task_add(
        title: str,
        workspace: str = "",
        home: str = "",
        notes: str = "",
        tags: list[str] | None = None,
        priority: str = "medium",
        due: str = "",
    ) -> dict:
        """Create a personal task."""
        effective_home = _effective_home(home, default_home)
        return task_add_tool(
            _effective_workspace(workspace, default_workspace, effective_home),
            title=title,
            notes=notes,
            tags=tags,
            priority=priority,
            due=due,
            home=effective_home,
        )

    @mcp.tool
    def alcove_task_list(
        workspace: str = "",
        status: str = "pending",
        home: str = "",
    ) -> dict:
        """List personal tasks."""
        effective_home = _effective_home(home, default_home)
        return task_list_tool(
            _effective_workspace(workspace, default_workspace, effective_home),
            status=status,
            home=effective_home,
        )

    @mcp.tool
    def alcove_idea_promote(
        idea_id: str,
        workspace: str = "",
        home: str = "",
        priority: str = "medium",
        due: str = "",
        notes: str = "",
    ) -> dict:
        """Promote an idea into a concrete task."""
        effective_home = _effective_home(home, default_home)
        return idea_promote_tool(
            _effective_workspace(workspace, default_workspace, effective_home),
            idea_id=idea_id,
            priority=priority,
            due=due,
            notes=notes,
            home=effective_home,
        )

    @mcp.tool
    def alcove_routine_add(
        title: str,
        workspace: str = "",
        home: str = "",
        notes: str = "",
        tags: list[str] | None = None,
        priority: str = "medium",
        every_days: int = 1,
        next_due: str = "",
    ) -> dict:
        """Create a recurring task template."""
        effective_home = _effective_home(home, default_home)
        return routine_add_tool(
            _effective_workspace(workspace, default_workspace, effective_home),
            title=title,
            notes=notes,
            tags=tags,
            priority=priority,
            every_days=every_days,
            next_due=next_due,
            home=effective_home,
        )

    @mcp.tool
    def alcove_routine_list(
        workspace: str = "",
        status: str = "active",
        home: str = "",
    ) -> dict:
        """List recurring task templates."""
        effective_home = _effective_home(home, default_home)
        return routine_list_tool(
            _effective_workspace(workspace, default_workspace, effective_home),
            status=status,
            home=effective_home,
        )

    @mcp.tool
    def alcove_routine_materialize_due(
        workspace: str = "",
        today: str = "",
        home: str = "",
    ) -> dict:
        """Create tasks for due recurring templates."""
        effective_home = _effective_home(home, default_home)
        return routine_materialize_due_tool(
            _effective_workspace(workspace, default_workspace, effective_home),
            today=today,
            home=effective_home,
        )

    @mcp.tool
    def alcove_link_source(
        item_path: str,
        topic: str,
        workspace: str = "",
        summary: str = "",
        create_concept: bool = False,
    ) -> dict:
        """Create a Source from an indexed external item."""
        return link_source_tool(
            workspace or _default_workspace(default_workspace),
            item_path=item_path,
            topic=topic,
            summary=summary,
            create_concept=create_concept,
        )

    @mcp.tool
    def alcove_gardener(workspace: str = "", prune: bool = False) -> dict:
        """Scan Alcove knowledge health and optionally prune safe issues."""
        return gardener_tool(
            workspace or _default_workspace(default_workspace),
            prune=prune,
        )

    return mcp


def run_mcp_server(
    default_workspace: str | None = None,
    default_home: str | None = None,
) -> None:
    create_mcp_server(default_workspace, default_home).run()


def _default_workspace(default_workspace: str | None) -> str:
    return default_workspace or "."


def _effective_home(home: str, default_home: str | None) -> str:
    return home or default_home or ""


def _effective_workspace(
    workspace: str,
    default_workspace: str | None,
    home: str = "",
) -> str:
    if workspace:
        return workspace
    if default_workspace:
        return default_workspace
    if home:
        return ""
    return "."


def _workspace_home(
    workspace: str = "",
    home: str = "",
) -> tuple[Workspace | None, AlcoveHome | None]:
    alcove_home = AlcoveHome.init(Path(home)) if home else None
    alcove = Workspace.discover(Path(workspace)) if workspace else None
    if alcove is None and alcove_home is None:
        alcove_home = AlcoveHome.init()
    return alcove, alcove_home


def _scope_payload(
    payload: dict,
    workspace: Workspace | None,
    home: AlcoveHome | None,
) -> dict:
    scoped = dict(payload)
    if workspace is not None:
        scoped["workspace"] = str(workspace.root)
    if home is not None:
        scoped["home"] = str(home.root)
    return scoped


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
