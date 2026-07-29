from __future__ import annotations

from alcove.pins import AddPinRequest, UpdatePinRequest


def pin_add_request(
    *,
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
) -> AddPinRequest:
    """Build the pin create request shared by MCP adapter surfaces."""
    return AddPinRequest(
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


def pin_update_request(
    *,
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
) -> UpdatePinRequest:
    """Build the pin update request shared by MCP adapter surfaces."""
    return UpdatePinRequest(
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
