from __future__ import annotations

from alcove.inbox_models import InboxNoteRequest


def inbox_note_request(
    *,
    name: str,
    topic: str,
    summary: str,
    tags: list[str] | None = None,
    selected_takeaways: list[str] | None = None,
    why: str = "",
    connection: str = "",
    action: str = "",
    personal_note: str = "",
    no_auto_tags: bool = False,
    supersede_similar: bool = False,
) -> InboxNoteRequest:
    """Build an inbox note request shared by MCP adapter surfaces."""
    return InboxNoteRequest(
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
    )
