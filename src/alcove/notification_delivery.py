from __future__ import annotations

from typing import Any

from alcove.markdown import normalize_slug


def notification_sinks(
    policy: dict[str, Any],
    *,
    default_type: str = "telegram",
    inheritable_keys: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    defaults = _inheritable_options(policy, inheritable_keys)
    raw_sinks = policy.get("sinks")
    if isinstance(raw_sinks, list) and raw_sinks:
        sinks = [{**defaults, **dict(sink)} for sink in raw_sinks if isinstance(sink, dict)]
        if sinks:
            return sinks
    channel = str(policy.get("channel") or default_type).strip() or default_type
    return [{**defaults, "type": channel}]


def notification_bool(
    policy: dict[str, Any],
    sink: dict[str, Any],
    key: str,
    default: bool,
) -> bool:
    if key in sink:
        return bool(sink[key])
    if key in policy:
        return bool(policy[key])
    return default


def notification_sink_label(
    sink: dict[str, Any],
    existing: dict[str, dict[str, Any]],
    *,
    default: str = "telegram",
) -> str:
    base = str(sink.get("id") or sink.get("name") or sink.get("type") or default).strip()
    label = normalize_slug(base) or default
    if label not in existing:
        return label
    index = 2
    while f"{label}-{index}" in existing:
        index += 1
    return f"{label}-{index}"


def combined_notification_status(results: dict[str, dict[str, Any]]) -> str:
    if not results:
        return "skipped"
    statuses = {str(result.get("status") or "skipped") for result in results.values()}
    if statuses == {"skipped"}:
        return "skipped"
    if statuses == {"sent"}:
        return "sent"
    if "sent" in statuses or "partial" in statuses:
        return "partial"
    if "failed" in statuses:
        return "failed"
    return "skipped"


def _inheritable_options(policy: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: policy[key] for key in keys if key in policy}
