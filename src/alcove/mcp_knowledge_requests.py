from __future__ import annotations

from alcove.knowledge import NoteSourceRequest, ReviseKnowledgeRequest


def note_source_request(
    *,
    platform: str,
    title: str,
    topic: str,
    resource: str = "",
    summary: str = "",
    tags: list[str] | None = None,
    published_date: str | None = None,
    create_concept: bool = True,
) -> NoteSourceRequest:
    """Build the OKF source request shared by MCP adapter surfaces."""
    return NoteSourceRequest(
        platform=platform,
        title=title,
        topic=topic,
        resource=resource,
        summary=summary,
        tags=tags or [],
        published_date=published_date,
        create_concept=create_concept,
    )


def revise_knowledge_request(
    *,
    path: str,
    summary: str = "",
    answer: str = "",
    append: str = "",
    tags: list[str] | None = None,
    source_refs: list[str] | None = None,
    reason: str = "",
    status: str = "",
) -> ReviseKnowledgeRequest:
    """Build the OKF revision request shared by MCP adapter surfaces."""
    return ReviseKnowledgeRequest(
        path=path,
        summary=summary,
        answer=answer,
        append=append,
        tags=tags or [],
        source_refs=source_refs or [],
        reason=reason,
        status=status,
    )
