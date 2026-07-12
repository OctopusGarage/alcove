from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from alcove.connectors.apple_notes import AppleNotesImportRequest, AppleNotesLocalImportRequest
from alcove.connectors.chrome_bookmarks import (
    ChromeBookmarksImportRequest,
    ChromeBookmarksLocalImportRequest,
)
from alcove.connectors.github_stars import GitHubStarsImportRequest, GitHubStarsUrlImportRequest
from alcove.inbox_models import InboxNoteRequest
from alcove.knowledge import (
    AddConceptRequest,
    AddEntityRequest,
    AddQuestionRequest,
    NoteSourceRequest,
    ReviseKnowledgeRequest,
)
from alcove.linking import LinkSourceRequest
from alcove.mounts import AddMountRequest
from alcove.pins import AddPinRequest, UpdatePinRequest
from alcove.projects import AddProjectRequest
from alcove.prompts import AddPromptRequest
from alcove.mcp_context import McpInvocationContext as _McpInvocationContext
from alcove.mcp_context import agent_payload as _agent_payload
from alcove.mcp_toolsets import resolve_mcp_toolset
from alcove.paths import compact_user_path
from alcove.search import SearchRequest
from alcove.tasks import AddIdeaRequest, AddRoutineRequest, AddTaskRequest


from alcove.mcp_direct_tools import (
    gardener_tool,
    get_topic_tool,
    idea_archive_tool,
    idea_edit_tool,
    idea_promote_routine_tool,
    idea_promote_tool,
    inbox_peek_tool,
    link_source_tool,
    mount_list_tool,
    note_source_tool,
    okf_catalog_build_tool,
    pin_add_tool,
    pin_get_tool,
    pin_rebuild_index_tool,
    pin_render_html_tool,
    pin_search_tool,
    pin_update_tool,
    project_add_tool,
    project_find_tool,
    prompt_get_tool,
    prompt_rebuild_index_tool,
    prompt_save_tool,
    revise_knowledge_tool,
    routine_add_tool,
    routine_archive_tool,
    routine_list_tool,
    routine_materialize_due_tool,
    routine_pause_tool,
    routine_resume_tool,
    search_tool,
    task_add_tool,
    task_digest_tool,
    task_edit_tool,
    task_list_tool,
)

__all__ = [
    "create_mcp_server",
    "gardener_tool",
    "get_topic_tool",
    "idea_archive_tool",
    "idea_edit_tool",
    "idea_promote_routine_tool",
    "idea_promote_tool",
    "inbox_peek_tool",
    "link_source_tool",
    "mount_list_tool",
    "note_source_tool",
    "okf_catalog_build_tool",
    "pin_add_tool",
    "pin_get_tool",
    "pin_rebuild_index_tool",
    "pin_render_html_tool",
    "pin_search_tool",
    "pin_update_tool",
    "project_add_tool",
    "project_find_tool",
    "prompt_get_tool",
    "prompt_rebuild_index_tool",
    "prompt_save_tool",
    "revise_knowledge_tool",
    "routine_add_tool",
    "routine_archive_tool",
    "routine_list_tool",
    "routine_materialize_due_tool",
    "routine_pause_tool",
    "routine_resume_tool",
    "run_mcp_server",
    "search_tool",
    "task_add_tool",
    "task_digest_tool",
    "task_edit_tool",
    "task_list_tool",
]


def create_mcp_server(
    default_workspace: str | None = None,
    default_home: str | None = None,
    toolset: str | None = None,
) -> Any:
    from fastmcp import FastMCP

    canonical_toolset, enabled_tools = resolve_mcp_toolset(toolset)
    mcp = FastMCP(f"alcove-{canonical_toolset}")
    context = _McpInvocationContext(default_workspace, default_home)

    def tool(fn: Any) -> Any:
        if fn.__name__ in enabled_tools:
            return mcp.tool(fn)
        return fn

    @mcp.resource(
        "alcove://home/config",
        name="alcove_home_config",
        mime_type="text/yaml",
        description="Alcove home configuration file.",
    )
    def alcove_home_config() -> str:
        path = _mcp_home_root(context) / "config.yml"
        return _read_text_or_empty(path)

    @mcp.resource(
        "alcove://planner/tasks",
        name="alcove_planner_tasks",
        mime_type="application/json",
        description="Alcove tasks, ideas, and routines source-of-truth JSON.",
    )
    def alcove_planner_tasks() -> str:
        path = _mcp_home_root(context) / "tasks" / "tasks.json"
        return _read_text_or_empty(path, default='{"tasks":[],"ideas":[],"routines":[]}\n')

    @mcp.resource(
        "alcove://radars/latest",
        name="alcove_latest_radar_reports",
        mime_type="application/json",
        description="Latest radar report files grouped by radar id.",
    )
    def alcove_latest_radar_reports() -> str:
        root = _mcp_home_root(context) / "radars" / "reports"
        return json.dumps(_latest_radar_reports(root), ensure_ascii=False, indent=2)

    @mcp.resource(
        "alcove://radars/{date}",
        name="alcove_radar_reports_by_date",
        mime_type="application/json",
        description="Radar report files for a date in YYYY-MM-DD format.",
    )
    def alcove_radar_reports_by_date(date: str) -> str:
        root = _mcp_home_root(context) / "radars" / "reports"
        return json.dumps(_radar_reports_for_date(root, date), ensure_ascii=False, indent=2)

    @mcp.prompt(
        "daily_briefing",
        description="Guide an agent through a daily Alcove briefing.",
    )
    def daily_briefing(focus: str = "", home: str = "") -> str:
        home_hint = home or context.default_home or "~/.alcove"
        focus_line = f"\nFocus: {focus}" if focus else ""
        return (
            "Prepare a concise daily briefing from Alcove.\n"
            f"Home: {home_hint}{focus_line}\n\n"
            "Use broad reads first: alcove_search, recent radar reports, planner tasks, "
            "pins, and managed knowledge-base evidence. Treat search results as leads; "
            "inspect OKF records or source files before making claims. Do not mutate data "
            "unless the user explicitly asks for a governed write."
        )

    @mcp.prompt(
        "todo_review",
        description="Guide an agent through reviewing Alcove tasks, ideas, and routines.",
    )
    def todo_review(home: str = "") -> str:
        home_hint = home or context.default_home or "~/.alcove"
        return (
            "Review Alcove planner state and produce an actionable summary.\n"
            f"Home: {home_hint}\n\n"
            "Read alcove://planner/tasks and use task/idea/routine tools for governed "
            "writes only after the user confirms changes. Group overdue, due soon, "
            "waiting ideas, and routines that need adjustment. Preserve task ids in the "
            "output so follow-up commands are easy."
        )

    @tool
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
        """Discover candidate Alcove records; treat results as leads, not final truth.

        For broad or ambiguous questions, inspect returned OKF paths, source refs,
        mount refs, connector items, and local files before answering.
        """
        return _agent_payload(
            context.scoped_app(workspace, home).search.search_payload(
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

    @tool
    def alcove_inbox_peek(workspace: str = "") -> dict[str, Any]:
        """Inspect the oldest pending Alcove inbox item."""
        return context.managed_app(workspace).inbox.inbox_peek_payload()

    @tool
    def alcove_mount_list(
        workspace: str = "",
        status: str = "active",
        home: str = "",
    ) -> dict[str, Any]:
        """List configured Alcove mounts."""
        return context.scoped_app(workspace, home).external.mount_list_payload(status)

    @tool
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
        """Record a source note through the governed OKF write path."""
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

    @tool
    def alcove_get_topic(
        topic: str,
        workspace: str = "",
        limit: int = 20,
    ) -> dict[str, Any]:
        """Return a topic overview and active Alcove docs for that topic."""
        return context.managed_app(workspace).knowledge.topic_payload(topic, limit)

    @tool
    def alcove_pin_add(
        title: str,
        workspace: str = "",
        home: str = "",
        description: str = "",
        summary: str = "",
        content: str = "",
        kind: str = "regular",
        tags: list[str] | None = None,
        priority: str = "medium",
        source_refs: list[str] | None = None,
        resources: list[str] | None = None,
        content_format: str = "text",
    ) -> dict[str, Any]:
        """Create a pinned personal note through the governed global write path."""
        return context.scoped_app(workspace, home).global_home.pin_add_payload(
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

    @tool
    def alcove_task_add(
        title: str,
        workspace: str = "",
        home: str = "",
        notes: str = "",
        tags: list[str] | None = None,
        priority: str = "medium",
        due: str = "",
    ) -> dict[str, Any]:
        """Create a personal task through the governed planner write path."""
        return context.scoped_app(workspace, home).global_home.task_add_payload(
            AddTaskRequest(
                title=title,
                notes=notes,
                tags=tags or [],
                priority=priority,
                due=due,
            )
        )

    @tool
    def alcove_task_list(
        workspace: str = "",
        status: str = "pending",
        home: str = "",
    ) -> dict[str, Any]:
        """List personal tasks."""
        return context.scoped_app(workspace, home).global_home.task_list_payload(status)

    @tool
    def alcove_task_edit(
        task_id: str,
        workspace: str = "",
        home: str = "",
        title: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
        priority: str | None = None,
        due: str | None = None,
    ) -> dict[str, Any]:
        """Edit a personal task through the governed planner write path."""
        return context.scoped_app(workspace, home).global_home.task_edit_payload(
            task_id,
            title=title,
            notes=notes,
            tags=tags,
            priority=priority,
            due=due,
        )

    @tool
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

    @tool
    def alcove_idea_edit(
        idea_id: str,
        workspace: str = "",
        home: str = "",
        title: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Edit a low-friction idea through the governed planner write path."""
        return context.scoped_app(workspace, home).global_home.idea_edit_payload(
            idea_id,
            title=title,
            notes=notes,
            tags=tags,
        )

    @tool
    def alcove_idea_archive(
        idea_id: str,
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Archive a low-friction idea."""
        return context.scoped_app(workspace, home).global_home.idea_archive_payload(idea_id)

    @tool
    def alcove_idea_promote_routine(
        idea_id: str,
        workspace: str = "",
        home: str = "",
        priority: str = "medium",
        next_due: str = "",
        notes: str = "",
        schedule: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Promote an idea into a recurring task template."""
        return context.scoped_app(workspace, home).global_home.idea_promote_routine_payload(
            idea_id=idea_id,
            priority=priority,
            next_due=next_due,
            notes=notes,
            schedule=schedule or {},
        )

    @tool
    def alcove_routine_add(
        title: str,
        workspace: str = "",
        home: str = "",
        notes: str = "",
        tags: list[str] | None = None,
        priority: str = "medium",
        every_days: int = 1,
        next_due: str = "",
        schedule: dict[str, Any] | None = None,
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
                schedule=schedule or {},
            )
        )

    @tool
    def alcove_routine_list(
        workspace: str = "",
        status: str = "active",
        home: str = "",
    ) -> dict[str, Any]:
        """List recurring task templates."""
        return context.scoped_app(workspace, home).global_home.routine_list_payload(status)

    @tool
    def alcove_routine_materialize_due(
        workspace: str = "",
        today: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Create tasks for due recurring templates."""
        return context.scoped_app(workspace, home).global_home.routine_materialize_due_payload(
            today
        )

    @tool
    def alcove_routine_pause(
        routine_id: str,
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Pause a recurring task template."""
        return context.scoped_app(workspace, home).global_home.routine_pause_payload(routine_id)

    @tool
    def alcove_routine_resume(
        routine_id: str,
        workspace: str = "",
        home: str = "",
        today: str = "",
    ) -> dict[str, Any]:
        """Resume a recurring task template."""
        return context.scoped_app(workspace, home).global_home.routine_resume_payload(
            routine_id,
            today=today,
        )

    @tool
    def alcove_routine_archive(
        routine_id: str,
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Archive a recurring task template."""
        return context.scoped_app(workspace, home).global_home.routine_archive_payload(routine_id)

    @tool
    def alcove_task_digest(
        workspace: str = "",
        home: str = "",
        period: str = "weekly",
        today: str = "",
        notify: bool = False,
    ) -> dict[str, Any]:
        """Build a planner digest, optionally notifying through configured credentials."""
        return context.scoped_app(workspace, home).global_home.task_digest_payload(
            period=period,
            today=today,
            notify=notify,
        )

    @tool
    def alcove_link_source(
        item_path: str,
        topic: str,
        workspace: str = "",
        home: str = "",
        summary: str = "",
        create_concept: bool = False,
    ) -> dict[str, Any]:
        """Promote indexed external evidence into a governed OKF Source."""
        return context.scoped_app(workspace, home).external.link_source_payload(
            LinkSourceRequest(
                item_path=item_path,
                topic=topic,
                summary=summary,
                create_concept=create_concept,
            )
        )

    @tool
    def alcove_gardener(workspace: str = "", prune: bool = False) -> dict[str, Any]:
        """Scan Alcove knowledge health and optionally prune safe issues."""
        return context.managed_app(workspace).system.gardener_payload(prune=prune)

    @tool
    def alcove_health(
        workspace: str = "",
        home: str = "",
        strict: bool = False,
        fix: bool = False,
    ) -> dict[str, Any]:
        """Check Alcove data, OKF files, and derived indexes across modules."""
        return context.scoped_app(workspace, home).system.health_payload(fix=fix, strict=strict)

    @tool
    def alcove_doctor(workspace: str = "") -> dict[str, Any]:
        """Check managed knowledge base health."""
        return context.managed_app(workspace).system.doctor_payload()

    @tool
    def alcove_validate(workspace: str = "", strict_quality: bool = False) -> dict[str, Any]:
        """Validate a managed knowledge base."""
        return context.managed_app(workspace).system.validate_payload(strict_quality=strict_quality)

    @tool
    def alcove_inbox_read(name: str, workspace: str = "") -> dict[str, Any]:
        """Read a managed knowledge base inbox item."""
        return context.managed_app(workspace).inbox.inbox_read_payload(name)

    @tool
    def alcove_inbox_manual_add(
        title: str,
        content: str,
        workspace: str = "",
        source: str = "",
    ) -> dict[str, Any]:
        """Add pasted or conversational content to a managed KB inbox."""
        return context.managed_app(workspace).inbox.inbox_manual_add_payload(title, content, source)

    @tool
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
        """Archive an inbox item as an OKF Source through the governed OKF write path."""
        return context.managed_app(workspace).inbox.inbox_archive_payload(
            name,
            topic,
            summary=summary,
            tags=tags,
            no_auto_tags=no_auto_tags,
            supersede_similar=supersede_similar,
            validate=validate,
        )

    @tool
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
        """Archive an inbox item and write an OKF note through the governed OKF write path."""
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

    @tool
    def alcove_inbox_todo(name: str, workspace: str = "", reason: str = "") -> dict[str, Any]:
        """Move an inbox item to managed knowledge base todo."""
        return context.managed_app(workspace).inbox.inbox_todo_payload(name, reason)

    @tool
    def alcove_inbox_delete(
        name: str,
        workspace: str = "",
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Delete or preview deleting an inbox item."""
        return context.managed_app(workspace).inbox.inbox_delete_payload(name, confirm=confirm)

    @tool
    def alcove_knowledge_add_note(
        topic: str,
        title: str,
        workspace: str = "",
        summary: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Add a standalone OKF Knowledge Concept through the governed OKF write path."""
        return context.managed_app(workspace).knowledge.knowledge_add_concept_payload(
            AddConceptRequest(topic=topic, title=title, summary=summary, tags=tags or [])
        )

    @tool
    def alcove_knowledge_revise(
        path: str,
        workspace: str = "",
        summary: str = "",
        answer: str = "",
        append: str = "",
        tags: list[str] | None = None,
        source_refs: list[str] | None = None,
        reason: str = "",
        status: str = "",
    ) -> dict[str, Any]:
        """Revise an existing OKF document through the governed OKF write path."""
        return context.managed_app(workspace).knowledge.knowledge_revise_payload(
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

    @tool
    def alcove_knowledge_add_question(
        topic: str,
        question: str,
        workspace: str = "",
        answer: str = "",
        tags: list[str] | None = None,
        source_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        """Add an OKF Question through the governed OKF write path."""
        return context.managed_app(workspace).knowledge.knowledge_add_question_payload(
            AddQuestionRequest(
                topic=topic,
                question=question,
                answer=answer,
                tags=tags or [],
                source_refs=source_refs or [],
            )
        )

    @tool
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
        """Add an OKF Entity through the governed OKF write path."""
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

    @tool
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

    @tool
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

    @tool
    def alcove_knowledge_delete(
        path: str,
        workspace: str = "",
        confirm: bool = False,
        reason: str = "",
    ) -> dict[str, Any]:
        """Preview or soft-delete a managed KB search result by path."""
        return context.managed_app(workspace).knowledge.knowledge_delete_payload(
            path,
            confirm=confirm,
            reason=reason,
        )

    @tool
    def alcove_knowledge_topics(workspace: str = "") -> dict[str, Any]:
        """List known OKF topics, tags, and domains."""
        return context.managed_app(workspace).knowledge.knowledge_topics_payload()

    @tool
    def alcove_pin_list(
        workspace: str = "",
        home: str = "",
        tag: str | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        """List pinned personal notes."""
        return context.scoped_app(workspace, home).global_home.pin_list_payload(tag, status)

    @tool
    def alcove_pin_get(
        pin_id: str,
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Get a pinned personal note."""
        return context.scoped_app(workspace, home).global_home.pin_get_payload(pin_id)

    @tool
    def alcove_pin_search(
        query: str = "",
        workspace: str = "",
        home: str = "",
        kind: str = "",
        tag: str = "",
        status: str = "active",
    ) -> dict[str, Any]:
        """Discover candidate pins; inspect full pin content before nuanced answers."""
        return context.scoped_app(workspace, home).global_home.pin_search_payload(
            query=query,
            kind=kind,
            tag=tag,
            status=status,
        )

    @tool
    def alcove_pin_update(
        pin_id: str,
        workspace: str = "",
        home: str = "",
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
    ) -> dict[str, Any]:
        """Update a pinned personal note through the governed global write path."""
        return context.scoped_app(workspace, home).global_home.pin_update_payload(
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

    @tool
    def alcove_pin_rebuild_index(
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Rebuild the pins index."""
        return context.scoped_app(workspace, home).global_home.pin_rebuild_index_payload()

    @tool
    def alcove_pin_render_html(
        workspace: str = "",
        home: str = "",
        output_path: str = "",
    ) -> dict[str, Any]:
        """Render the pins HTML board."""
        return context.scoped_app(workspace, home).global_home.pin_render_html_payload(output_path)

    @tool
    def alcove_pin_archive(
        pin_id: str,
        workspace: str = "",
        home: str = "",
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Archive or preview archiving a pin."""
        return context.scoped_app(workspace, home).global_home.pin_archive_payload(pin_id, confirm)

    @tool
    def alcove_project_add(
        alias: str,
        path: str,
        workspace: str = "",
        home: str = "",
        note: str = "",
    ) -> dict[str, Any]:
        """Create or update a global project alias."""
        return context.scoped_app(workspace, home).global_home.project_add_payload(
            AddProjectRequest(alias=alias, path=path, note=note)
        )

    @tool
    def alcove_project_get(
        alias: str,
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Get a global project alias."""
        return context.scoped_app(workspace, home).global_home.project_get_payload(alias)

    @tool
    def alcove_project_find(
        keyword: str,
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Find global project aliases or scanned root projects."""
        return context.scoped_app(workspace, home).global_home.project_find_payload(keyword)

    @tool
    def alcove_project_list(workspace: str = "", home: str = "") -> dict[str, Any]:
        """List global project aliases."""
        return context.scoped_app(workspace, home).global_home.project_list_payload()

    @tool
    def alcove_project_remove(
        alias: str,
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Remove a global project alias."""
        return context.scoped_app(workspace, home).global_home.project_remove_payload(alias)

    @tool
    def alcove_project_roots_set(
        roots: list[str],
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Configure roots scanned by project find."""
        return context.scoped_app(workspace, home).global_home.project_roots_set_payload(roots)

    @tool
    def alcove_prompt_save(
        title: str,
        content: str,
        workspace: str = "",
        home: str = "",
        description: str = "",
        tags: list[str] | None = None,
        use_cases: list[str] | None = None,
        source_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        """Save or update a reusable global prompt through the governed prompt write path."""
        return context.scoped_app(workspace, home).global_home.prompt_save_payload(
            AddPromptRequest(
                title=title,
                content=content,
                description=description,
                tags=tags or [],
                use_cases=use_cases or [],
                source_refs=source_refs or [],
            )
        )

    @tool
    def alcove_prompt_search(
        query: str = "",
        workspace: str = "",
        home: str = "",
        tag: str = "",
        status: str = "active",
    ) -> dict[str, Any]:
        """Discover candidate global prompts; inspect the full prompt before reuse."""
        return context.scoped_app(workspace, home).global_home.prompt_search_payload(
            query=query,
            tag=tag,
            status=status,
        )

    @tool
    def alcove_prompt_get(
        prompt_id: str,
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Get a reusable global prompt."""
        return context.scoped_app(workspace, home).global_home.prompt_get_payload(prompt_id)

    @tool
    def alcove_prompt_archive(
        prompt_id: str,
        workspace: str = "",
        home: str = "",
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Archive or preview archiving a reusable global prompt."""
        return context.scoped_app(workspace, home).global_home.prompt_archive_payload(
            prompt_id,
            confirm,
        )

    @tool
    def alcove_prompt_tags(workspace: str = "", home: str = "") -> dict[str, Any]:
        """List reusable global prompt tags."""
        return context.scoped_app(workspace, home).global_home.prompt_tags_payload()

    @tool
    def alcove_prompt_rebuild_index(workspace: str = "", home: str = "") -> dict[str, Any]:
        """Rebuild the reusable global prompt index."""
        return context.scoped_app(workspace, home).global_home.prompt_rebuild_index_payload()

    @tool
    def alcove_okf_catalog_build(workspace: str = "", home: str = "") -> dict[str, Any]:
        """Build the derived global OKF catalog used as a Markdown entry for AI-led reads."""
        return context.scoped_app(workspace, home).system.okf_catalog_build_payload()

    @tool
    def alcove_idea_add(
        title: str,
        workspace: str = "",
        home: str = "",
        notes: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Add a low-friction idea through the governed planner write path."""
        return context.scoped_app(workspace, home).global_home.idea_add_payload(
            AddIdeaRequest(title=title, notes=notes, tags=tags or [])
        )

    @tool
    def alcove_idea_list(
        workspace: str = "",
        home: str = "",
        status: str = "active",
    ) -> dict[str, Any]:
        """List low-friction ideas."""
        return context.scoped_app(workspace, home).global_home.idea_list_payload(status)

    @tool
    def alcove_task_complete(
        task_id: str,
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Complete a task."""
        return context.scoped_app(workspace, home).global_home.task_complete_payload(task_id)

    @tool
    def alcove_task_cancel(
        task_id: str,
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Cancel a task."""
        return context.scoped_app(workspace, home).global_home.task_cancel_payload(task_id)

    @tool
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

    @tool
    def alcove_mount_scan(
        workspace: str = "",
        home: str = "",
        mount_id: str | None = None,
        include_diagnostics: bool = False,
    ) -> dict[str, Any]:
        """Refresh mount indexes so AI-led investigation has current local-file evidence."""
        return context.scoped_app(workspace, home).external.mount_scan_payload(
            mount_id,
            include_diagnostics=include_diagnostics,
        )

    @tool
    def alcove_connector_fetch(
        item_path: str, workspace: str = "", home: str = ""
    ) -> dict[str, Any]:
        """Lazy-fetch detail for an indexed connector candidate before final synthesis."""
        return context.scoped_app(workspace, home).external.connector_fetch_payload(item_path)

    @tool
    def alcove_connector_status(
        workspace: str = "",
        home: str = "",
        connector: str = "",
    ) -> dict[str, Any]:
        """Show registered connector sources and freshness status."""
        return _agent_payload(
            context.scoped_app(workspace, home).external.connector_status_payload(connector)
        )

    @tool
    def alcove_connector_refresh(
        workspace: str = "",
        home: str = "",
        connector: str = "",
        source_id: str = "",
        stale_only: bool = True,
    ) -> dict[str, Any]:
        """Refresh connector indexes so candidate discovery uses current external evidence."""
        return context.scoped_app(workspace, home).external.connector_refresh_payload(
            connector=connector,
            source_id=source_id,
            stale_only=stale_only,
        )

    @tool
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

    @tool
    def alcove_connector_apple_notes_import_local(
        workspace: str = "",
        home: str = "",
        export_dir: str = "",
        source_id: str = "local",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Export local Notes.app notes into Alcove, then index them."""
        return context.scoped_app(workspace, home).external.apple_notes_import_local_payload(
            AppleNotesLocalImportRequest(
                export_dir=export_dir,
                source_id=source_id,
                tags=tags or [],
            )
        )

    @tool
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

    @tool
    def alcove_connector_github_stars_import_url(
        source: str,
        workspace: str = "",
        home: str = "",
        export_file: str = "",
        tags: list[str] | None = None,
        limit: int = 0,
        max_pages: int = 0,
    ) -> dict[str, Any]:
        """Fetch starred repositories from a GitHub stars page or username, then index them."""
        return context.scoped_app(workspace, home).external.github_stars_import_url_payload(
            GitHubStarsUrlImportRequest(
                source=source,
                export_file=export_file,
                tags=tags or [],
                limit=limit,
                max_pages=max_pages,
            )
        )

    @tool
    def alcove_connector_chrome_bookmarks_index(
        export_file: str,
        workspace: str = "",
        home: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Index a Chrome Bookmarks JSON file or Netscape bookmarks HTML export."""
        return context.scoped_app(workspace, home).external.chrome_bookmarks_index_payload(
            ChromeBookmarksImportRequest(export_file=export_file, tags=tags or [])
        )

    @tool
    def alcove_connector_chrome_bookmarks_import_local(
        workspace: str = "",
        home: str = "",
        source_file: str = "",
        profile: str = "Default",
        source_id: str = "default",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Index the local Chrome profile Bookmarks file and register it for refresh."""
        return context.scoped_app(workspace, home).external.chrome_bookmarks_import_local_payload(
            ChromeBookmarksLocalImportRequest(
                source_file=source_file,
                profile=profile,
                source_id=source_id,
                tags=tags or [],
            )
        )

    @tool
    def alcove_export_global(output_dir: str, home: str = "") -> dict[str, Any]:
        """Export Alcove Home global data."""
        return context.scoped_app("", home).system.export_global_payload(output_dir)

    @tool
    def alcove_export_kb(kb: str, output_dir: str, home: str = "") -> dict[str, Any]:
        """Export a registered managed knowledge base."""
        return context.scoped_app("", home).system.export_kb_payload(kb, output_dir)

    @tool
    def alcove_export_all(output_dir: str, home: str = "") -> dict[str, Any]:
        """Export Alcove Home and all registered managed knowledge bases."""
        return context.scoped_app("", home).system.export_all_payload(output_dir)

    return mcp


def run_mcp_server(
    default_workspace: str | None = None,
    default_home: str | None = None,
    toolset: str | None = None,
) -> None:
    create_mcp_server(default_workspace, default_home, toolset=toolset).run()


def _mcp_home_root(context: _McpInvocationContext, home: str = "") -> Path:
    app = context.scoped_app("", home)
    if app.runtime.home is None:
        return Path("~/.alcove").expanduser()
    return app.runtime.home.root


def _read_text_or_empty(path: Path, *, default: str = "") -> str:
    if not path.is_file():
        return default
    return path.read_text(encoding="utf-8")


def _latest_radar_reports(root: Path) -> dict[str, Any]:
    reports: dict[str, dict[str, str]] = {}
    if not root.is_dir():
        return {"reports": reports}
    for radar_root in sorted(path for path in root.iterdir() if path.is_dir()):
        latest = _latest_report_pair(radar_root)
        if latest:
            reports[radar_root.name] = latest
    return {"reports": reports}


def _radar_reports_for_date(root: Path, date: str) -> dict[str, Any]:
    reports: dict[str, dict[str, str]] = {}
    if not root.is_dir():
        return {"date": date, "reports": reports}
    for radar_root in sorted(path for path in root.iterdir() if path.is_dir()):
        paths = {}
        for suffix in ("md", "html", "ai.md"):
            path = radar_root / f"{date}.{suffix}"
            if path.is_file():
                paths[suffix] = compact_user_path(path)
        if paths:
            reports[radar_root.name] = paths
    return {"date": date, "reports": reports}


def _latest_report_pair(radar_root: Path) -> dict[str, str]:
    candidates = sorted(radar_root.glob("*.md"))
    latest_date = ""
    for path in candidates:
        if path.name.endswith(".ai.md"):
            continue
        latest_date = max(latest_date, path.stem)
    if not latest_date:
        return {}
    payload: dict[str, str] = {"date": latest_date}
    for suffix in ("md", "html", "ai.md"):
        path = radar_root / f"{latest_date}.{suffix}"
        if path.is_file():
            payload[suffix] = compact_user_path(path)
    return payload
