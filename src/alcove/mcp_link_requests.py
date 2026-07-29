from __future__ import annotations

from alcove.linking import LinkSourceRequest


def link_source_request(
    *,
    item_path: str,
    topic: str,
    summary: str = "",
    create_concept: bool = False,
) -> LinkSourceRequest:
    """Build the external link request shared by MCP adapter surfaces."""
    return LinkSourceRequest(
        item_path=item_path,
        topic=topic,
        summary=summary,
        create_concept=create_concept,
    )
