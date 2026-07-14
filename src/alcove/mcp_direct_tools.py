from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from alcove.application import AlcoveApplication
from alcove.knowledge import NoteSourceRequest, ReviseKnowledgeRequest
from alcove.linking import LinkSourceRequest
from alcove.mcp_command_hints import command_hints_tool as command_hints_tool
from alcove.mcp_context import McpInvocationContext, agent_payload
from alcove.pins import AddPinRequest, UpdatePinRequest
from alcove.projects import AddProjectRequest
from alcove.prompts import AddPromptRequest
from alcove.search import SearchRequest
from alcove.tasks import AddRoutineRequest, AddTaskRequest


@dataclass(frozen=True)
class McpDirectToolRuntime:
    """Context-aware runtime seam for direct MCP helper calls in tests and adapters."""

    context: McpInvocationContext

    @classmethod
    def from_defaults(
        cls,
        *,
        default_workspace: str | None = None,
        default_home: str | None = None,
    ) -> "McpDirectToolRuntime":
        return cls(McpInvocationContext(default_workspace, default_home))

    def app(self, workspace: str = "", home: str = "") -> AlcoveApplication:
        return self.context.scoped_app(workspace, home)

    def managed_app(self, workspace: str = "") -> AlcoveApplication:
        return self.context.managed_app(workspace)


DEFAULT_DIRECT_TOOL_RUNTIME = McpDirectToolRuntime.from_defaults()


def _app(workspace: str = "", home: str = "") -> AlcoveApplication:
    return DEFAULT_DIRECT_TOOL_RUNTIME.app(workspace, home)


def _managed_app(workspace: str = "") -> AlcoveApplication:
    return DEFAULT_DIRECT_TOOL_RUNTIME.managed_app(workspace)


def direct_tool_runtime(
    *,
    default_workspace: str | None = None,
    default_home: str | None = None,
) -> McpDirectToolRuntime:
    """Create a context-bound runtime for tests or custom MCP adapters."""
    return McpDirectToolRuntime.from_defaults(
        default_workspace=default_workspace,
        default_home=default_home,
    )


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
) -> dict[str, Any]:
    """Search Alcove knowledge, pins, ideas, and tasks."""
    return agent_payload(
        _app(workspace, home).search.search_payload(
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
            ),
            surface="mcp",
        )
    )


def inbox_peek_tool(workspace: str) -> dict[str, Any]:
    """Inspect the oldest pending Alcove inbox item."""
    return _managed_app(workspace).inbox.inbox_peek_payload()


def mount_list_tool(workspace: str = "", status: str = "active", home: str = "") -> dict[str, Any]:
    """List configured Alcove mounts."""
    return _app(workspace, home).external.mount_list_payload(status)


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
) -> dict[str, Any]:
    """Record a source note in Alcove knowledge."""
    return _managed_app(workspace).knowledge.note_source_payload(
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


def get_topic_tool(workspace: str, topic: str, limit: int = 20) -> dict[str, Any]:
    """Return a topic overview and active Alcove docs for that topic."""
    return _managed_app(workspace).knowledge.topic_payload(topic, limit)


def revise_knowledge_tool(
    workspace: str,
    path: str,
    summary: str = "",
    answer: str = "",
    append: str = "",
    tags: list[str] | None = None,
    source_refs: list[str] | None = None,
    reason: str = "",
    status: str = "",
) -> dict[str, Any]:
    """Revise an existing OKF knowledge document."""
    return _managed_app(workspace).knowledge.knowledge_revise_payload(
        ReviseKnowledgeRequest(
            path=path,
            summary=summary,
            answer=answer,
            append=append,
            tags=tags or [],
            source_refs=source_refs or [],
            reason=reason,
            status=status,
        )
    )


def pin_add_tool(
    workspace: str,
    title: str,
    description: str = "",
    summary: str = "",
    content: str = "",
    kind: str = "regular",
    tags: list[str] | None = None,
    priority: str = "medium",
    source_refs: list[str] | None = None,
    resources: list[str] | None = None,
    content_format: str = "text",
    home: str = "",
) -> dict[str, Any]:
    """Create a pinned personal note."""
    return _app(workspace, home).global_home.pin_add_payload(
        AddPinRequest(
            title=title,
            description=description,
            summary=summary,
            content=content,
            kind=kind,
            tags=tags or [],
            priority=priority,
            source_refs=source_refs or [],
            resources=resources or [],
            content_format=content_format,
        )
    )


def pin_get_tool(workspace: str, pin_id: str, home: str = "") -> dict[str, Any]:
    """Get a pinned personal note."""
    return _app(workspace, home).global_home.pin_get_payload(pin_id)


def pin_search_tool(
    workspace: str,
    query: str = "",
    kind: str = "",
    tag: str = "",
    status: str = "active",
    home: str = "",
) -> dict[str, Any]:
    """Search pinned personal notes."""
    return _app(workspace, home).global_home.pin_search_payload(
        query=query, kind=kind, tag=tag, status=status
    )


def pin_update_tool(
    workspace: str,
    pin_id: str,
    title: str | None = None,
    description: str | None = None,
    summary: str | None = None,
    content: str | None = None,
    kind: str | None = None,
    tags: list[str] | None = None,
    priority: str | None = None,
    source_refs: list[str] | None = None,
    resources: list[str] | None = None,
    status: str | None = None,
    content_format: str | None = None,
    home: str = "",
) -> dict[str, Any]:
    """Update a pinned personal note."""
    return _app(workspace, home).global_home.pin_update_payload(
        UpdatePinRequest(
            pin_id=pin_id,
            title=title,
            description=description,
            summary=summary,
            content=content,
            kind=kind,
            tags=tags,
            priority=priority,
            source_refs=source_refs,
            resources=resources,
            status=status,
            content_format=content_format,
        )
    )


def pin_rebuild_index_tool(workspace: str = "", home: str = "") -> dict[str, Any]:
    """Rebuild the pins index."""
    return _app(workspace, home).global_home.pin_rebuild_index_payload()


def pin_render_html_tool(
    workspace: str = "",
    home: str = "",
    output_path: str = "",
) -> dict[str, Any]:
    """Render the pins HTML board."""
    return _app(workspace, home).global_home.pin_render_html_payload(output_path)


def project_add_tool(
    workspace: str,
    alias: str,
    path: str,
    note: str = "",
    home: str = "",
) -> dict[str, Any]:
    """Create or update a global project alias."""
    return _app(workspace, home).global_home.project_add_payload(
        AddProjectRequest(alias=alias, path=path, note=note)
    )


def project_find_tool(workspace: str, keyword: str, home: str = "") -> dict[str, Any]:
    """Find registered projects or scanned root projects."""
    return _app(workspace, home).global_home.project_find_payload(keyword)


def prompt_save_tool(
    workspace: str,
    title: str = "",
    content: str = "",
    description: str = "",
    tags: list[str] | None = None,
    use_cases: list[str] | None = None,
    source_refs: list[str] | None = None,
    home: str = "",
    proposal_id: str = "",
    force: bool = False,
) -> dict[str, Any]:
    """Save a reusable global prompt from a proposal, or force a direct write."""
    return _app(workspace, home).global_home.prompt_save_payload(
        (
            AddPromptRequest(
                title=title,
                content=content,
                description=description,
                tags=tags or [],
                use_cases=use_cases or [],
                source_refs=source_refs or [],
            )
            if not proposal_id
            else None
        ),
        proposal_id=proposal_id,
        force=force,
    )


def prompt_propose_tool(
    workspace: str,
    content: str,
    title: str = "",
    description: str = "",
    tags: list[str] | None = None,
    use_cases: list[str] | None = None,
    source_refs: list[str] | None = None,
    home: str = "",
) -> dict[str, Any]:
    """Prepare, improve, deduplicate, and classify a reusable prompt before saving."""
    return _app(workspace, home).global_home.prompt_propose_payload(
        AddPromptRequest(
            title=title,
            content=content,
            description=description,
            tags=tags or [],
            use_cases=use_cases or [],
            source_refs=source_refs or [],
        )
    )


def prompt_get_tool(workspace: str, prompt_id: str, home: str = "") -> dict[str, Any]:
    """Get a reusable global prompt."""
    return _app(workspace, home).global_home.prompt_get_payload(prompt_id)


def prompt_rebuild_index_tool(workspace: str = "", home: str = "") -> dict[str, Any]:
    """Rebuild the reusable global prompt index."""
    return _app(workspace, home).global_home.prompt_rebuild_index_payload()


def okf_catalog_build_tool(
    workspace: str = "",
    home: str = "",
    include_all_status: bool = False,
) -> dict[str, Any]:
    """Build the derived global OKF catalog for AI-led reads."""
    return _app(workspace, home).system.okf_catalog_build_payload(
        include_all_status=include_all_status
    )


def task_add_tool(
    workspace: str,
    title: str,
    notes: str = "",
    tags: list[str] | None = None,
    priority: str = "medium",
    due: str = "",
    home: str = "",
) -> dict[str, Any]:
    """Create a personal task."""
    return _app(workspace, home).global_home.task_add_payload(
        AddTaskRequest(
            title=title,
            notes=notes,
            tags=tags or [],
            priority=priority,
            due=due,
        )
    )


def task_list_tool(workspace: str = "", status: str = "pending", home: str = "") -> dict[str, Any]:
    """List personal tasks."""
    return _app(workspace, home).global_home.task_list_payload(status)


def task_edit_tool(
    workspace: str,
    task_id: str,
    title: str | None = None,
    notes: str | None = None,
    tags: list[str] | None = None,
    priority: str | None = None,
    due: str | None = None,
    home: str = "",
) -> dict[str, Any]:
    """Edit a personal task."""
    return _app(workspace, home).global_home.task_edit_payload(
        task_id,
        title=title,
        notes=notes,
        tags=tags,
        priority=priority,
        due=due,
    )


def idea_promote_tool(
    workspace: str,
    idea_id: str,
    priority: str = "medium",
    due: str = "",
    notes: str = "",
    home: str = "",
) -> dict[str, Any]:
    """Promote an idea into a concrete task."""
    return _app(workspace, home).global_home.idea_promote_payload(
        idea_id,
        priority=priority,
        due=due,
        notes=notes,
    )


def idea_edit_tool(
    workspace: str,
    idea_id: str,
    title: str | None = None,
    notes: str | None = None,
    tags: list[str] | None = None,
    home: str = "",
) -> dict[str, Any]:
    """Edit a low-friction idea."""
    return _app(workspace, home).global_home.idea_edit_payload(
        idea_id, title=title, notes=notes, tags=tags
    )


def idea_archive_tool(workspace: str, idea_id: str, home: str = "") -> dict[str, Any]:
    """Archive a low-friction idea."""
    return _app(workspace, home).global_home.idea_archive_payload(idea_id)


def idea_promote_routine_tool(
    workspace: str,
    idea_id: str,
    priority: str = "medium",
    next_due: str = "",
    notes: str = "",
    schedule: dict[str, Any] | None = None,
    home: str = "",
) -> dict[str, Any]:
    """Promote an idea into a recurring task template."""
    return _app(workspace, home).global_home.idea_promote_routine_payload(
        idea_id,
        priority=priority,
        next_due=next_due,
        notes=notes,
        schedule=schedule or {},
    )


def routine_add_tool(
    workspace: str,
    title: str,
    notes: str = "",
    tags: list[str] | None = None,
    priority: str = "medium",
    every_days: int = 1,
    next_due: str = "",
    schedule: dict[str, Any] | None = None,
    home: str = "",
) -> dict[str, Any]:
    """Create a recurring task template."""
    return _app(workspace, home).global_home.routine_add_payload(
        AddRoutineRequest(
            title=title,
            notes=notes,
            tags=tags or [],
            priority=priority,
            every_days=every_days,
            next_due=next_due,
            schedule=schedule or {},
        )
    )


def routine_list_tool(
    workspace: str = "",
    status: str = "active",
    home: str = "",
) -> dict[str, Any]:
    """List recurring task templates."""
    return _app(workspace, home).global_home.routine_list_payload(status)


def routine_materialize_due_tool(
    workspace: str = "",
    today: str = "",
    home: str = "",
) -> dict[str, Any]:
    """Create tasks for due recurring templates."""
    return _app(workspace, home).global_home.routine_materialize_due_payload(today)


def routine_pause_tool(workspace: str, routine_id: str, home: str = "") -> dict[str, Any]:
    """Pause a recurring task template."""
    return _app(workspace, home).global_home.routine_pause_payload(routine_id)


def routine_resume_tool(
    workspace: str,
    routine_id: str,
    today: str = "",
    home: str = "",
) -> dict[str, Any]:
    """Resume a recurring task template."""
    return _app(workspace, home).global_home.routine_resume_payload(routine_id, today=today)


def routine_archive_tool(workspace: str, routine_id: str, home: str = "") -> dict[str, Any]:
    """Archive a recurring task template."""
    return _app(workspace, home).global_home.routine_archive_payload(routine_id)


def task_digest_tool(
    workspace: str = "",
    period: str = "weekly",
    today: str = "",
    notify: bool = False,
    home: str = "",
) -> dict[str, Any]:
    """Build a planner digest, optionally notifying through configured credentials."""
    return _app(workspace, home).global_home.task_digest_payload(
        period=period, today=today, notify=notify
    )


def link_source_tool(
    workspace: str,
    item_path: str,
    topic: str,
    summary: str = "",
    create_concept: bool = False,
    home: str = "",
) -> dict[str, Any]:
    """Create a Source from an indexed external item."""
    return _app(workspace, home).external.link_source_payload(
        LinkSourceRequest(
            item_path=item_path,
            topic=topic,
            summary=summary,
            create_concept=create_concept,
        )
    )


def gardener_tool(workspace: str, prune: bool = False) -> dict[str, Any]:
    """Scan Alcove knowledge health and optionally prune safe issues."""
    return _managed_app(workspace).system.gardener_payload(prune=prune)
