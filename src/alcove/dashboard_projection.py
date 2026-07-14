from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from alcove.home import AlcoveHome
from alcove.markdown import normalize_slug

DASHBOARD_TIMEZONE = timezone(timedelta(hours=8))


class DashboardProjection:
    """Private projection rules for dashboard snapshot rows and counts."""

    def __init__(self, home: AlcoveHome) -> None:
        self.home = home

    def task_dict(self, task: Any) -> dict[str, Any]:
        row = asdict(task)
        source_routine_id = str(row.get("source_routine_id") or "")
        row["generated_from_routine"] = bool(source_routine_id)
        row["instance_due"] = row.get("due") if source_routine_id else ""
        row["display_title"] = (
            f"{row.get('title', '')} (routine due)" if source_routine_id else row.get("title", "")
        )
        due = str(row.get("due") or "")
        status = str(row.get("status") or "")
        overdue_days = self.overdue_days(due) if status == "pending" else 0
        row["overdue"] = overdue_days > 0
        row["overdue_days"] = overdue_days
        row["due_state"] = "overdue" if overdue_days > 0 else ("due" if due else "")
        return row

    def overdue_days(self, due: str) -> int:
        if not due:
            return 0
        try:
            due_date = datetime.fromisoformat(due).date()
        except ValueError:
            return 0
        today = datetime.now(DASHBOARD_TIMEZONE).date()
        return max((today - due_date).days, 0)

    def theme_pin_dict(self, pin: Any) -> dict[str, Any]:
        data = self.pin_dict(pin)
        data["sections"] = self.sections_from_content(pin.content)
        data["raw_excerpt"] = pin.content[:360].strip()
        return data

    def sections_from_content(self, content: str) -> list[dict[str, str]]:
        sections: list[dict[str, str]] = []
        current_heading = ""
        current_body: list[str] = []
        for line in content.splitlines():
            if line.startswith("### "):
                if current_heading or current_body:
                    sections.append(
                        {
                            "heading": current_heading or "Notes",
                            "body": "\n".join(current_body).strip(),
                        }
                    )
                current_heading = line[4:].strip()
                current_body = []
            elif line.startswith("## "):
                continue
            elif current_heading:
                current_body.append(line)
        if current_heading or current_body:
            sections.append(
                {
                    "heading": current_heading or "Notes",
                    "body": "\n".join(current_body).strip(),
                }
            )
        return [section for section in sections if section["body"]]

    def pin_dict(self, pin: Any) -> dict[str, Any]:
        return {
            "id": pin.id,
            "title": pin.title,
            "kind": pin.kind,
            "summary": pin.summary,
            "content": pin.content,
            "tags": pin.tags,
            "priority": pin.priority,
            "status": pin.status,
            "source_refs": pin.source_refs,
            "resources": pin.resources,
            "updated_at": pin.updated_at,
        }

    def modules(self, counts: dict[str, int]) -> list[dict[str, Any]]:
        return [
            {
                "id": "pins",
                "title": "Pins",
                "subtitle": "Stable references and themes to revisit",
                "href": "/pins",
                "metric": counts["pin_collections"],
                "detail": (
                    f"{self.count_phrase(counts['pin_collections'], 'displayed collection')} "
                    f"({counts['regular_theme_pins']} regular / "
                    f"{counts['todo_theme_pins']} TODO); "
                    f"{self.count_phrase(counts['pins'], 'active pin')}"
                ),
            },
            {
                "id": "knowledge",
                "title": "Knowledge",
                "subtitle": "Managed KBs, mounts, and connectors",
                "href": "/knowledge",
                "metric": (
                    counts["knowledge_items"] + counts["mount_items"] + counts["connector_items"]
                ),
                "detail": (
                    f"{self.count_phrase(counts['knowledge_items'], 'managed note')}, "
                    f"{self.count_phrase(counts['mount_items'], 'mounted file')}, "
                    f"{self.count_phrase(counts['connector_items'], 'connector item')}; "
                    f"{self.count_phrase(counts['knowledge_bases'], 'managed KB')}, "
                    f"{self.count_phrase(counts['mounts'], 'mount')}, "
                    f"{self.count_phrase(counts['connectors'], 'connector')}"
                ),
            },
            {
                "id": "planner",
                "title": "Planner",
                "subtitle": "Tasks, ideas, and routines",
                "href": "/planner",
                "metric": (
                    counts["pending_tasks"] + counts["active_ideas"] + counts["active_routines"]
                ),
                "detail": (
                    f"{counts['direct_pending_tasks']} direct pending / "
                    f"{counts['routine_due_tasks']} routine due; "
                    f"{counts['active_ideas']} active ideas / "
                    f"{counts['active_routines']} active routines"
                ),
            },
            {
                "id": "library",
                "title": "Library",
                "subtitle": "Prompts and project shortcuts",
                "href": "/library",
                "metric": counts["prompts"] + counts["projects"],
                "detail": (
                    f"{self.count_phrase(counts['prompts'], 'prompt')} / "
                    f"{self.count_phrase(counts['projects'], 'project shortcut')}"
                ),
            },
            {
                "id": "activity",
                "title": "Activity",
                "subtitle": "Recent events and file changes",
                "href": "/activity",
                "metric": counts["activity_events"],
                "detail": (
                    "Events and inferred changes; "
                    f"{counts['blog_sources_active']} active blog monitors"
                ),
            },
            {
                "id": "radars",
                "title": "Radars",
                "subtitle": "Scheduled information discovery",
                "href": "/radars",
                "metric": counts["radars"],
                "detail": (
                    f"{self.count_phrase(counts['radars'], 'active radar')} / "
                    f"{self.count_phrase(counts['radars_current'], 'current report')} / "
                    f"{self.count_phrase(counts['radars_stale'], 'stale report')}"
                ),
            },
            {
                "id": "usage",
                "title": "Usage",
                "subtitle": "Search, actions, and data health",
                "href": "/usage",
                "metric": counts["usage_events"],
                "detail": f"{counts['usage_events']} local usage events",
            },
        ]

    def health_summary(
        self,
        *,
        knowledge_rows: list[dict[str, Any]],
        connector_rows: list[dict[str, Any]],
        mount_rows: list[dict[str, Any]],
        usage_summary: dict[str, Any],
    ) -> dict[str, Any]:
        data_sources: list[dict[str, Any]] = []
        for row in knowledge_rows:
            item_count = int(row.get("item_count") or 0)
            data_sources.append(
                {
                    "kind": "managed-kb",
                    "name": str(row.get("name") or ""),
                    "status": "ok" if item_count > 0 else "empty",
                    "item_count": item_count,
                    "inbox_count": int(row.get("inbox_count") or 0),
                    "updated_at": str(row.get("updated_at") or ""),
                    "command_hint": self.health_command_hint(
                        "managed-kb", str(row.get("name") or "")
                    ),
                }
            )
        for row in mount_rows:
            item_count = int(row.get("item_count") or 0)
            mount_id = str(row.get("id") or "")
            data_sources.append(
                {
                    "kind": "mount",
                    "name": str(row.get("name") or mount_id),
                    "status": "ok" if item_count > 0 else "empty",
                    "item_count": item_count,
                    "updated_at": str(row.get("updated_at") or ""),
                    "command_hint": self.health_command_hint("mount", mount_id),
                }
            )
        for row in connector_rows:
            raw_status = str(row.get("freshness_status") or row.get("status") or "")
            item_count = int(row.get("item_count") or row.get("count") or 0)
            connector = str(row.get("connector") or row.get("id") or "")
            data_sources.append(
                {
                    "kind": "connector",
                    "name": connector,
                    "status": raw_status or ("ok" if item_count > 0 else "empty"),
                    "item_count": item_count,
                    "updated_at": str(row.get("updated_at") or row.get("checked_at") or ""),
                    "command_hint": self.health_command_hint("connector", connector),
                }
            )
        totals = {
            "managed_kbs": len(knowledge_rows),
            "managed_items": sum(int(row.get("item_count") or 0) for row in knowledge_rows),
            "mounts": len(mount_rows),
            "mount_items": sum(int(row.get("item_count") or 0) for row in mount_rows),
            "connectors": len(connector_rows),
            "connector_items": sum(
                int(row.get("item_count") or row.get("count") or 0) for row in connector_rows
            ),
            "usage_events": int(usage_summary.get("total_events") or 0),
        }
        issue_count = len(
            [
                row
                for row in data_sources
                if str(row.get("status") or "") in {"empty", "stale", "error"}
            ]
        )
        stats_root = self.home.paths().stats
        daily_root = stats_root / "daily"
        return {
            "status": "needs-attention" if issue_count else "ok",
            "issue_count": issue_count,
            "totals": totals,
            "stats": {
                "summary_exists": (stats_root / "summary.json").is_file(),
                "daily_rollups": (
                    len(list(daily_root.glob("*.json"))) if daily_root.is_dir() else 0
                ),
                "updated_at": self.latest_mtime(
                    [path for path in [stats_root / "summary.json"] if path.is_file()]
                ),
            },
            "data_sources": data_sources,
        }

    def health_command_hint(self, kind: str, identifier: str) -> str:
        value = identifier.strip()
        if not value:
            return ""
        if kind == "managed-kb":
            return f"alcove validate --kb {value} --json"
        value = normalize_slug(value)
        if not value:
            return ""
        if kind == "mount":
            return f"alcove mount scan {value} --json"
        if kind == "connector":
            return f"alcove connector refresh --connector {value} --json"
        return ""

    def count_phrase(self, count: int, singular: str, plural: str | None = None) -> str:
        label = singular if count == 1 else plural or f"{singular}s"
        return f"{count} {label}"

    def latest_mtime(self, paths: list[Path]) -> str:
        if not paths:
            return ""
        return datetime.fromtimestamp(max(path.stat().st_mtime for path in paths), UTC).isoformat(
            timespec="seconds"
        )
