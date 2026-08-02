from __future__ import annotations

from typing import Any

from alcove.mcp_context import McpInvocationContext
from alcove.mcp_inbox_requests import inbox_note_request
from alcove.mcp_knowledge_requests import (
    add_concept_request,
    add_entity_request,
    add_question_request,
    note_source_request,
    revise_knowledge_request,
)
from alcove.mcp_registrar import McpToolRegistrar


def register_mcp_managed_kb_tools(
    registrar: McpToolRegistrar,
    context: McpInvocationContext,
) -> None:
    tool = registrar.tool

    @tool
    def alcove_inbox_peek(workspace: str = "") -> dict[str, Any]:
        """Inspect the oldest pending Alcove inbox item."""
        return context.managed_app(workspace).inbox.inbox_peek_payload()

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
            note_source_request(
                platform=platform,
                title=title,
                topic=topic,
                resource=resource,
                summary=summary,
                tags=tags,
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
            inbox_note_request(
                name=name,
                topic=topic,
                summary=summary,
                tags=tags,
                selected_takeaways=selected_takeaways,
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
            add_concept_request(topic=topic, title=title, summary=summary, tags=tags)
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
            revise_knowledge_request(
                path=path,
                summary=summary,
                answer=answer,
                append=append,
                tags=tags,
                source_refs=source_refs,
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
            add_question_request(
                topic=topic,
                question=question,
                answer=answer,
                tags=tags,
                source_refs=source_refs,
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
            add_entity_request(
                topic=topic,
                name=name,
                kind=kind,
                summary=summary,
                use_cases=use_cases,
                open_questions=open_questions,
                tags=tags,
                source_refs=source_refs,
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
