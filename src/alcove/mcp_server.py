from __future__ import annotations

from pathlib import Path
from typing import Any

from alcove.application import AlcoveApplication
from alcove.connectors.apple_notes import AppleNotesImportRequest
from alcove.connectors.github_stars import GitHubStarsImportRequest
from alcove.inbox_models import InboxNoteRequest
from alcove.knowledge import (
    AddConceptRequest,
    AddEntityRequest,
    AddQuestionRequest,
    NoteSourceRequest,
)
from alcove.linking import LinkSourceRequest
from alcove.mounts import AddMountRequest
from alcove.pins import AddPinRequest
from alcove.runtime import AlcoveRuntime
from alcove.search import SearchRequest
from alcove.tasks import AddIdeaRequest, AddRoutineRequest, AddTaskRequest


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
    return (
        _McpInvocationContext()
        .app(workspace, home)
        .search.search_payload(
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
    )


def inbox_peek_tool(workspace: str) -> dict[str, Any]:
    """Inspect the oldest pending Alcove inbox item."""
    return _McpInvocationContext().managed_app(workspace).inbox.inbox_peek_payload()


def mount_list_tool(workspace: str = "", status: str = "active", home: str = "") -> dict[str, Any]:
    """List configured Alcove mounts."""
    return _McpInvocationContext().app(workspace, home).external.mount_list_payload(status)


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
    return (
        _McpInvocationContext()
        .managed_app(workspace)
        .knowledge.note_source_payload(
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
    )


def get_topic_tool(workspace: str, topic: str, limit: int = 20) -> dict[str, Any]:
    """Return a topic overview and active Alcove docs for that topic."""
    return _McpInvocationContext().managed_app(workspace).knowledge.topic_payload(topic, limit)


def pin_add_tool(
    workspace: str,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    priority: str = "medium",
    source_refs: list[str] | None = None,
    home: str = "",
) -> dict[str, Any]:
    """Create a pinned personal note."""
    return (
        _McpInvocationContext()
        .app(workspace, home)
        .global_home.pin_add_payload(
            AddPinRequest(
                title=title,
                description=description,
                tags=tags or [],
                priority=priority,
                source_refs=source_refs or [],
            )
        )
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
    return (
        _McpInvocationContext()
        .app(workspace, home)
        .global_home.task_add_payload(
            AddTaskRequest(
                title=title,
                notes=notes,
                tags=tags or [],
                priority=priority,
                due=due,
            )
        )
    )


def task_list_tool(workspace: str = "", status: str = "pending", home: str = "") -> dict[str, Any]:
    """List personal tasks."""
    return _McpInvocationContext().app(workspace, home).global_home.task_list_payload(status)


def idea_promote_tool(
    workspace: str,
    idea_id: str,
    priority: str = "medium",
    due: str = "",
    notes: str = "",
    home: str = "",
) -> dict[str, Any]:
    """Promote an idea into a concrete task."""
    return (
        _McpInvocationContext()
        .app(workspace, home)
        .global_home.idea_promote_payload(
            idea_id,
            priority=priority,
            due=due,
            notes=notes,
        )
    )


def routine_add_tool(
    workspace: str,
    title: str,
    notes: str = "",
    tags: list[str] | None = None,
    priority: str = "medium",
    every_days: int = 1,
    next_due: str = "",
    home: str = "",
) -> dict[str, Any]:
    """Create a recurring task template."""
    return (
        _McpInvocationContext()
        .app(workspace, home)
        .global_home.routine_add_payload(
            AddRoutineRequest(
                title=title,
                notes=notes,
                tags=tags or [],
                priority=priority,
                every_days=every_days,
                next_due=next_due,
            )
        )
    )


def routine_list_tool(
    workspace: str = "",
    status: str = "active",
    home: str = "",
) -> dict[str, Any]:
    """List recurring task templates."""
    return _McpInvocationContext().app(workspace, home).global_home.routine_list_payload(status)


def routine_materialize_due_tool(
    workspace: str = "",
    today: str = "",
    home: str = "",
) -> dict[str, Any]:
    """Create tasks for due recurring templates."""
    return (
        _McpInvocationContext()
        .app(workspace, home)
        .global_home.routine_materialize_due_payload(today)
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
    return (
        _McpInvocationContext()
        .app(workspace, home)
        .external.link_source_payload(
            LinkSourceRequest(
                item_path=item_path,
                topic=topic,
                summary=summary,
                create_concept=create_concept,
            )
        )
    )


def gardener_tool(workspace: str, prune: bool = False) -> dict[str, Any]:
    """Scan Alcove knowledge health and optionally prune safe issues."""
    return _McpInvocationContext().managed_app(workspace).system.gardener_payload(prune=prune)


def create_mcp_server(
    default_workspace: str | None = None,
    default_home: str | None = None,
) -> Any:
    from fastmcp import FastMCP

    mcp = FastMCP("alcove")
    context = _McpInvocationContext(default_workspace, default_home)

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
    ) -> dict[str, Any]:
        """Search Alcove knowledge, pins, ideas, and tasks."""
        return context.scoped_app(workspace, home).search.search_payload(
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

    @mcp.tool
    def alcove_inbox_peek(workspace: str = "") -> dict[str, Any]:
        """Inspect the oldest pending Alcove inbox item."""
        return context.managed_app(workspace).inbox.inbox_peek_payload()

    @mcp.tool
    def alcove_mount_list(
        workspace: str = "",
        status: str = "active",
        home: str = "",
    ) -> dict[str, Any]:
        """List configured Alcove mounts."""
        return context.scoped_app(workspace, home).external.mount_list_payload(status)

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
    ) -> dict[str, Any]:
        """Record a source note in Alcove knowledge."""
        return context.managed_app(workspace).knowledge.note_source_payload(
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

    @mcp.tool
    def alcove_get_topic(
        topic: str,
        workspace: str = "",
        limit: int = 20,
    ) -> dict[str, Any]:
        """Return a topic overview and active Alcove docs for that topic."""
        return context.managed_app(workspace).knowledge.topic_payload(topic, limit)

    @mcp.tool
    def alcove_pin_add(
        title: str,
        workspace: str = "",
        home: str = "",
        description: str = "",
        tags: list[str] | None = None,
        priority: str = "medium",
        source_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a pinned personal note."""
        return context.scoped_app(workspace, home).global_home.pin_add_payload(
            AddPinRequest(
                title=title,
                description=description,
                tags=tags or [],
                priority=priority,
                source_refs=source_refs or [],
            )
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
    ) -> dict[str, Any]:
        """Create a personal task."""
        return context.scoped_app(workspace, home).global_home.task_add_payload(
            AddTaskRequest(
                title=title,
                notes=notes,
                tags=tags or [],
                priority=priority,
                due=due,
            )
        )

    @mcp.tool
    def alcove_task_list(
        workspace: str = "",
        status: str = "pending",
        home: str = "",
    ) -> dict[str, Any]:
        """List personal tasks."""
        return context.scoped_app(workspace, home).global_home.task_list_payload(status)

    @mcp.tool
    def alcove_idea_promote(
        idea_id: str,
        workspace: str = "",
        home: str = "",
        priority: str = "medium",
        due: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        """Promote an idea into a concrete task."""
        return context.scoped_app(workspace, home).global_home.idea_promote_payload(
            idea_id=idea_id,
            priority=priority,
            due=due,
            notes=notes,
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
    ) -> dict[str, Any]:
        """Create a recurring task template."""
        return context.scoped_app(workspace, home).global_home.routine_add_payload(
            AddRoutineRequest(
                title=title,
                notes=notes,
                tags=tags or [],
                priority=priority,
                every_days=every_days,
                next_due=next_due,
            )
        )

    @mcp.tool
    def alcove_routine_list(
        workspace: str = "",
        status: str = "active",
        home: str = "",
    ) -> dict[str, Any]:
        """List recurring task templates."""
        return context.scoped_app(workspace, home).global_home.routine_list_payload(status)

    @mcp.tool
    def alcove_routine_materialize_due(
        workspace: str = "",
        today: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Create tasks for due recurring templates."""
        return context.scoped_app(workspace, home).global_home.routine_materialize_due_payload(
            today
        )

    @mcp.tool
    def alcove_link_source(
        item_path: str,
        topic: str,
        workspace: str = "",
        home: str = "",
        summary: str = "",
        create_concept: bool = False,
    ) -> dict[str, Any]:
        """Create a Source from an indexed external item."""
        return context.scoped_app(workspace, home).external.link_source_payload(
            LinkSourceRequest(
                item_path=item_path,
                topic=topic,
                summary=summary,
                create_concept=create_concept,
            )
        )

    @mcp.tool
    def alcove_gardener(workspace: str = "", prune: bool = False) -> dict[str, Any]:
        """Scan Alcove knowledge health and optionally prune safe issues."""
        return context.managed_app(workspace).system.gardener_payload(prune=prune)

    @mcp.tool
    def alcove_doctor(workspace: str = "") -> dict[str, Any]:
        """Check managed knowledge base health."""
        return context.managed_app(workspace).system.doctor_payload()

    @mcp.tool
    def alcove_validate(workspace: str = "", strict_quality: bool = False) -> dict[str, Any]:
        """Validate a managed knowledge base."""
        return context.managed_app(workspace).system.validate_payload(strict_quality=strict_quality)

    @mcp.tool
    def alcove_inbox_read(name: str, workspace: str = "") -> dict[str, Any]:
        """Read a managed knowledge base inbox item."""
        return context.managed_app(workspace).inbox.inbox_read_payload(name)

    @mcp.tool
    def alcove_inbox_manual_add(
        title: str,
        content: str,
        workspace: str = "",
        source: str = "",
    ) -> dict[str, Any]:
        """Add manual content to a managed knowledge base inbox."""
        return context.managed_app(workspace).inbox.inbox_manual_add_payload(title, content, source)

    @mcp.tool
    def alcove_inbox_archive(
        name: str,
        topic: str,
        workspace: str = "",
        summary: str = "",
        tags: list[str] | None = None,
        no_auto_tags: bool = False,
        supersede_similar: bool = False,
        validate: bool = False,
    ) -> dict[str, Any]:
        """Archive an inbox item as an OKF Source."""
        return context.managed_app(workspace).inbox.inbox_archive_payload(
            name,
            topic,
            summary=summary,
            tags=tags,
            no_auto_tags=no_auto_tags,
            supersede_similar=supersede_similar,
            validate=validate,
        )

    @mcp.tool
    def alcove_inbox_note(
        name: str,
        topic: str,
        summary: str,
        workspace: str = "",
        tags: list[str] | None = None,
        selected_takeaways: list[str] | None = None,
        why: str = "",
        connection: str = "",
        action: str = "",
        personal_note: str = "",
        no_auto_tags: bool = False,
        supersede_similar: bool = False,
        validate: bool = False,
    ) -> dict[str, Any]:
        """Archive an inbox item and write a knowledge note."""
        return context.managed_app(workspace).inbox.inbox_note_payload(
            InboxNoteRequest(
                name=name,
                topic=topic,
                summary=summary,
                tags=tags or [],
                selected_takeaways=selected_takeaways or [],
                why=why,
                connection=connection,
                action=action,
                personal_note=personal_note,
                no_auto_tags=no_auto_tags,
                supersede_similar=supersede_similar,
            ),
            validate=validate,
        )

    @mcp.tool
    def alcove_inbox_todo(name: str, workspace: str = "", reason: str = "") -> dict[str, Any]:
        """Move an inbox item to managed knowledge base todo."""
        return context.managed_app(workspace).inbox.inbox_todo_payload(name, reason)

    @mcp.tool
    def alcove_inbox_delete(
        name: str,
        workspace: str = "",
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Delete or preview deleting an inbox item."""
        return context.managed_app(workspace).inbox.inbox_delete_payload(name, confirm=confirm)

    @mcp.tool
    def alcove_knowledge_add_note(
        topic: str,
        title: str,
        workspace: str = "",
        summary: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Add a standalone OKF Knowledge Concept."""
        return context.managed_app(workspace).knowledge.knowledge_add_concept_payload(
            AddConceptRequest(topic=topic, title=title, summary=summary, tags=tags or [])
        )

    @mcp.tool
    def alcove_knowledge_add_question(
        topic: str,
        question: str,
        workspace: str = "",
        answer: str = "",
        tags: list[str] | None = None,
        source_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        """Add an OKF Question."""
        return context.managed_app(workspace).knowledge.knowledge_add_question_payload(
            AddQuestionRequest(
                topic=topic,
                question=question,
                answer=answer,
                tags=tags or [],
                source_refs=source_refs or [],
            )
        )

    @mcp.tool
    def alcove_knowledge_add_entity(
        topic: str,
        name: str,
        workspace: str = "",
        kind: str = "object",
        summary: str = "",
        use_cases: str = "",
        open_questions: str = "",
        tags: list[str] | None = None,
        source_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        """Add an OKF Entity."""
        return context.managed_app(workspace).knowledge.knowledge_add_entity_payload(
            AddEntityRequest(
                topic=topic,
                name=name,
                kind=kind,
                summary=summary,
                use_cases=use_cases,
                open_questions=open_questions,
                tags=tags or [],
                source_refs=source_refs or [],
            )
        )

    @mcp.tool
    def alcove_knowledge_promote(
        source: str,
        workspace: str = "",
        topic: str = "",
        summary: str = "",
    ) -> dict[str, Any]:
        """Promote an OKF Source into a Knowledge Concept."""
        return context.managed_app(workspace).knowledge.knowledge_promote_payload(
            source,
            topic=topic,
            summary=summary,
        )

    @mcp.tool
    def alcove_knowledge_refresh(
        topic: str,
        workspace: str = "",
        in_place: bool = False,
        summary: str = "",
    ) -> dict[str, Any]:
        """Refresh a topic from active sources."""
        return context.managed_app(workspace).knowledge.knowledge_refresh_payload(
            topic,
            in_place=in_place,
            summary=summary,
        )

    @mcp.tool
    def alcove_knowledge_topics(workspace: str = "") -> dict[str, Any]:
        """List known OKF topics, tags, and domains."""
        return context.managed_app(workspace).knowledge.knowledge_topics_payload()

    @mcp.tool
    def alcove_pin_list(
        workspace: str = "",
        home: str = "",
        tag: str | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        """List pinned personal notes."""
        return context.scoped_app(workspace, home).global_home.pin_list_payload(tag, status)

    @mcp.tool
    def alcove_pin_archive(
        pin_id: str,
        workspace: str = "",
        home: str = "",
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Archive or preview archiving a pin."""
        return context.scoped_app(workspace, home).global_home.pin_archive_payload(pin_id, confirm)

    @mcp.tool
    def alcove_idea_add(
        title: str,
        workspace: str = "",
        home: str = "",
        notes: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Add a low-friction idea."""
        return context.scoped_app(workspace, home).global_home.idea_add_payload(
            AddIdeaRequest(title=title, notes=notes, tags=tags or [])
        )

    @mcp.tool
    def alcove_idea_list(
        workspace: str = "",
        home: str = "",
        status: str = "active",
    ) -> dict[str, Any]:
        """List low-friction ideas."""
        return context.scoped_app(workspace, home).global_home.idea_list_payload(status)

    @mcp.tool
    def alcove_task_complete(
        task_id: str,
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Complete a task."""
        return context.scoped_app(workspace, home).global_home.task_complete_payload(task_id)

    @mcp.tool
    def alcove_task_cancel(
        task_id: str,
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Cancel a task."""
        return context.scoped_app(workspace, home).global_home.task_cancel_payload(task_id)

    @mcp.tool
    def alcove_mount_add(
        path: str,
        workspace: str = "",
        home: str = "",
        name: str = "",
        mount_type: str = "local-folder",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Add a mounted external source."""
        return context.scoped_app(workspace, home).external.mount_add_payload(
            AddMountRequest(path=path, name=name, mount_type=mount_type, tags=tags or [])
        )

    @mcp.tool
    def alcove_mount_scan(
        workspace: str = "",
        home: str = "",
        mount_id: str | None = None,
    ) -> dict[str, Any]:
        """Scan mounted external sources."""
        return context.scoped_app(workspace, home).external.mount_scan_payload(mount_id)

    @mcp.tool
    def alcove_connector_fetch(
        item_path: str, workspace: str = "", home: str = ""
    ) -> dict[str, Any]:
        """Fetch detail for an indexed connector item."""
        return context.scoped_app(workspace, home).external.connector_fetch_payload(item_path)

    @mcp.tool
    def alcove_connector_apple_notes_index(
        export_dir: str,
        workspace: str = "",
        home: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Index a deterministic Apple Notes export directory."""
        return context.scoped_app(workspace, home).external.apple_notes_index_payload(
            AppleNotesImportRequest(export_dir=export_dir, tags=tags or [])
        )

    @mcp.tool
    def alcove_connector_github_stars_index(
        export_file: str,
        workspace: str = "",
        home: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Index a GitHub Stars JSON export."""
        return context.scoped_app(workspace, home).external.github_stars_index_payload(
            GitHubStarsImportRequest(export_file=export_file, tags=tags or [])
        )

    @mcp.tool
    def alcove_export_global(output_dir: str, home: str = "") -> dict[str, Any]:
        """Export Alcove Home global data."""
        return context.scoped_app("", home).system.export_global_payload(output_dir)

    @mcp.tool
    def alcove_export_kb(kb: str, output_dir: str, home: str = "") -> dict[str, Any]:
        """Export a registered managed knowledge base."""
        return context.scoped_app("", home).system.export_kb_payload(kb, output_dir)

    @mcp.tool
    def alcove_export_all(output_dir: str, home: str = "") -> dict[str, Any]:
        """Export Alcove Home and all registered managed knowledge bases."""
        return context.scoped_app("", home).system.export_all_payload(output_dir)

    return mcp


def run_mcp_server(
    default_workspace: str | None = None,
    default_home: str | None = None,
) -> None:
    create_mcp_server(default_workspace, default_home).run()


class _McpInvocationContext:
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
