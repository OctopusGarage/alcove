from __future__ import annotations


VALID_AGENT_TARGETS = {"codex", "claude"}


def resolve_agent_targets(targets: list[str] | None) -> list[str]:
    if not targets or "all" in targets:
        return ["codex", "claude"]
    normalized: list[str] = []
    for target in targets:
        for item in str(target).split(","):
            value = item.strip().lower()
            if not value:
                continue
            if value not in VALID_AGENT_TARGETS:
                raise ValueError(f"Unknown install target: {value}")
            if value not in normalized:
                normalized.append(value)
    return normalized
