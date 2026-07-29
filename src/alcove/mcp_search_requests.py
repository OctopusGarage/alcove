from __future__ import annotations

from alcove.search import SearchRequest


def search_request(
    *,
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
) -> SearchRequest:
    """Build the search request shared by MCP adapter surfaces."""
    return SearchRequest(
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
