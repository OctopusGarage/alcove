from __future__ import annotations

import re
from typing import Any


def build_dashboard_search_index(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for pin in snapshot["pins"]["all"]:
        rows.append(
            {
                "type": "pin",
                "title": str(pin["title"]),
                "text": _deduplicated_search_text(
                    [
                        str(pin["title"]),
                        str(pin["summary"]),
                        " ".join(pin["tags"]),
                        str(pin["content"]),
                    ]
                ),
                "href": "/pins",
            }
        )
    for prompt in snapshot.get("prompts", []):
        rows.append(
            {
                "type": "prompt",
                "title": str(prompt.get("title") or ""),
                "text": "\n".join(
                    str(part)
                    for part in [
                        prompt.get("description"),
                        prompt.get("content"),
                        " ".join(prompt.get("use_cases") or []),
                        " ".join(prompt.get("tags") or []),
                        prompt.get("status"),
                    ]
                    if part
                ),
                "href": "/library",
            }
        )
    for task in snapshot["tasks"]["pending"]:
        rows.append(
            {
                "type": "task",
                "title": str(task.get("display_title") or task.get("title") or ""),
                "text": "\n".join(
                    str(part)
                    for part in [
                        task.get("notes"),
                        task.get("status"),
                        task.get("priority"),
                        task.get("due"),
                        task.get("due_state"),
                        f"overdue {task.get('overdue_days')} days" if task.get("overdue") else "",
                        "generated_from_routine" if task.get("generated_from_routine") else "",
                        task.get("source_routine_id"),
                        task.get("instance_due"),
                    ]
                    if part
                ),
                "href": "/planner",
            }
        )
    for idea in snapshot["tasks"].get("ideas", []):
        rows.append(
            {
                "type": "idea",
                "title": str(idea.get("title") or ""),
                "text": str(idea.get("notes") or ""),
                "href": "/planner",
            }
        )
    for routine in snapshot["tasks"].get("routines", []):
        rows.append(
            {
                "type": "routine",
                "title": str(routine.get("title") or ""),
                "text": str(routine.get("notes") or ""),
                "href": "/planner",
            }
        )
    for project in snapshot.get("projects", []):
        rows.append(
            {
                "type": "project",
                "title": str(project.get("alias") or ""),
                "text": "\n".join(
                    str(part)
                    for part in [
                        project.get("alias"),
                        project.get("target_label"),
                        project.get("note"),
                    ]
                    if part
                ),
                "href": "/library",
            }
        )
    for module in snapshot["modules"]:
        rows.append(
            {
                "type": "module",
                "title": str(module["title"]),
                "text": f"{module['subtitle']} {module['detail']}",
                "href": str(module["href"]),
            }
        )
    for radar in snapshot.get("radars", []):
        rows.append(
            {
                "type": "radar",
                "title": str(radar.get("name") or radar.get("id") or ""),
                "text": " ".join(
                    [
                        str(radar.get("id") or ""),
                        str(radar.get("status") or ""),
                        "scheduled" if radar.get("schedule_enabled") else "manual",
                        f"{radar.get('source_count', 0)} sources",
                        str(radar.get("report_label") or ""),
                        " ".join(radar.get("tags") or []),
                    ]
                ),
                "href": "/radars",
            }
        )
    rows.extend(_knowledge_rows(snapshot))
    rows.extend(_source_rows(snapshot))
    return rows


def _knowledge_rows(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for kb in snapshot.get("knowledge", {}).get("managed", []):
        omitted_titles = [
            str(item.get("title") or "")
            for item in kb.get("omitted_items") or []
            if isinstance(item, dict)
        ]
        omitted_count = int(kb.get("omitted_item_count") or 0)
        text_parts = [
            f"{kb.get('item_count', 0)} knowledge items",
            f"{kb.get('inbox_count', 0)} inbox items",
            f"{kb.get('archive_count', 0)} archived items",
        ]
        if omitted_count > 0:
            text_parts.insert(1, f"{omitted_count} omitted from snapshot list")
            if omitted_titles:
                text_parts.insert(2, "omitted: " + ", ".join(omitted_titles))
        rows.append(
            {
                "type": "knowledge-base",
                "title": str(kb.get("name") or ""),
                "text": " ".join(text_parts),
                "href": "/knowledge",
            }
        )
        for item in kb.get("search_items") or kb.get("items", []):
            if _is_structural_knowledge_item(item):
                continue
            rows.append(_external_row("knowledge-item", item))
    return rows


def _source_rows(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for mount in snapshot.get("sources", {}).get("mounts", []):
        rows.append(
            {
                "type": "mount",
                "title": str(mount.get("name") or mount.get("id") or ""),
                "text": " ".join(
                    [
                        str(mount.get("type") or ""),
                        str(mount.get("status") or ""),
                        f"{mount.get('count', 0)} items",
                    ]
                ),
                "href": "/knowledge",
            }
        )
        for item in mount.get("items", []):
            rows.append(_external_row("mount-item", item))
    for connector in snapshot.get("sources", {}).get("connectors", []):
        rows.append(
            {
                "type": "connector",
                "title": str(connector.get("id") or connector.get("connector") or ""),
                "text": " ".join(
                    [
                        _public_resource(str(connector.get("source") or "")),
                        str(connector.get("status") or ""),
                        f"{connector.get('count', 0)} items",
                    ]
                ),
                "href": "/knowledge",
            }
        )
        for item in connector.get("items", []):
            rows.append(_external_row("connector-item", item))
    return rows


def _external_row(row_type: str, item: dict[str, Any]) -> dict[str, str]:
    return {
        "type": row_type,
        "title": str(item.get("title") or ""),
        "text": "\n".join(
            str(part)
            for part in [
                item.get("type"),
                _public_resource(str(item.get("resource") or "")),
                item.get("status"),
                _search_text_summary(str(item.get("notes") or "")),
            ]
            if part
        ),
        "href": "/knowledge",
    }


def _is_structural_knowledge_item(item: dict[str, Any]) -> bool:
    relative_path = str(item.get("relative_path") or "")
    return relative_path == "knowledge/index.md" or relative_path.startswith(
        (
            "knowledge/domains/",
            "knowledge/tags/",
            "knowledge/topics/",
        )
    )


def _search_text_summary(value: str, max_chars: int = 280) -> str:
    lines: list[str] = []
    in_frontmatter = False
    for line in value.splitlines():
        stripped = line.strip()
        if stripped == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter or not stripped:
            continue
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
            if not stripped:
                continue
        stripped = re.sub(r"^[-*]\s+", "", stripped)
        stripped = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", stripped)
        stripped = stripped.strip("`")
        if stripped.startswith(("type:", "status:", "domain:", "topic:")):
            continue
        lines.append(stripped)
        if len(" ".join(lines)) >= max_chars:
            break
    text = " ".join(lines).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _deduplicated_search_text(parts: list[str]) -> str:
    rows: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for line in part.splitlines() or [part]:
            cleaned = line.strip()
            if not cleaned:
                continue
            key = " ".join(cleaned.casefold().split())
            if not key or key in seen:
                continue
            rows.append(cleaned)
            seen.add(key)
    return "\n".join(rows)


def _public_resource(value: str) -> str:
    if value.startswith(("~", "/", ".")):
        return ""
    return value
