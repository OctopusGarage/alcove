from __future__ import annotations

from alcove.knowledge import (
    AddConceptRequest,
    AddEntityRequest,
    AddQuestionRequest,
    NoteSourceRequest,
    ReviseKnowledgeRequest,
)


def add_concept_request(
    *,
    topic: str,
    title: str,
    summary: str = "",
    tags: list[str] | None = None,
) -> AddConceptRequest:
    """Build the OKF concept request shared by MCP adapter surfaces."""
    return AddConceptRequest(topic=topic, title=title, summary=summary, tags=tags or [])


def add_question_request(
    *,
    topic: str,
    question: str,
    answer: str = "",
    tags: list[str] | None = None,
    source_refs: list[str] | None = None,
) -> AddQuestionRequest:
    """Build the OKF question request shared by MCP adapter surfaces."""
    return AddQuestionRequest(
        topic=topic,
        question=question,
        answer=answer,
        tags=tags or [],
        source_refs=source_refs or [],
    )


def add_entity_request(
    *,
    topic: str,
    name: str,
    kind: str = "object",
    summary: str = "",
    use_cases: str = "",
    open_questions: str = "",
    tags: list[str] | None = None,
    source_refs: list[str] | None = None,
) -> AddEntityRequest:
    """Build the OKF entity request shared by MCP adapter surfaces."""
    return AddEntityRequest(
        topic=topic,
        name=name,
        kind=kind,
        summary=summary,
        use_cases=use_cases,
        open_questions=open_questions,
        tags=tags or [],
        source_refs=source_refs or [],
    )


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
