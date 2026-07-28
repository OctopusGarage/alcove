from __future__ import annotations

from typing import Any

from alcove.prompts import AddPromptRequest


def prompt_request(
    *,
    title: str = "",
    content: str = "",
    description: str = "",
    tags: list[str] | None = None,
    use_cases: list[str] | None = None,
    source_refs: list[str] | None = None,
    kind: str = "full_prompt",
    domain: str = "",
    intent: str = "",
    surfaces: list[str] | None = None,
    triggers: list[str] | None = None,
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
    quality: dict[str, Any] | None = None,
) -> AddPromptRequest:
    """Build the prompt write request shared by MCP adapter surfaces."""
    return AddPromptRequest(
        title=title,
        content=content,
        description=description,
        tags=tags or [],
        use_cases=use_cases or [],
        source_refs=source_refs or [],
        kind=kind,
        domain=domain,
        intent=intent,
        surfaces=surfaces or [],
        triggers=triggers or [],
        inputs=inputs or [],
        outputs=outputs or [],
        quality=quality or {},
    )
