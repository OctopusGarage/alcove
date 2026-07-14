from __future__ import annotations

from pathlib import Path
from typing import Any

from alcove.health_types import HealthIssue


class HealthPlannerHygieneMixin:
    """Planner-specific hygiene checks used by Alcove Home health."""

    def _check_planner_fixture_records(
        self: Any,
        path: Path,
        issues: list[HealthIssue],
        counts: dict[str, int],
        *,
        fixture_context: bool = False,
    ) -> None:
        payload = self._read_json(path, issues, "tasks")
        if not isinstance(payload, dict):
            counts["planner_fixture_records"] = 0
            return
        flagged = 0
        for section, active_statuses in (
            ("tasks", {"pending"}),
            ("ideas", {"active"}),
            ("routines", {"active"}),
        ):
            for item in self._dict_list(payload, section):
                if not isinstance(item, dict):
                    continue
                status = str(item.get("status") or "")
                if status not in active_statuses:
                    continue
                if not self._is_fixture_planner_record(item):
                    continue
                flagged += 1
                if fixture_context:
                    continue
                record_id = str(item.get("id") or "<missing-id>")
                title = str(item.get("title") or "<missing-title>")
                self._issue(
                    issues,
                    "warning",
                    "tasks",
                    "active_fixture_record",
                    path,
                    f"Active planner {section[:-1]} looks like a test fixture: {record_id} ({title}).",
                    "Archive/cancel the fixture record or run tests against an isolated Alcove Home.",
                )
        counts["planner_fixture_records"] = flagged
        counts["planner_fixture_context"] = 1 if fixture_context else 0

    def _is_fixture_planner_record(self: Any, item: dict[str, Any]) -> bool:
        record_id = str(item.get("id") or "").strip().lower()
        title = str(item.get("title") or "").strip().lower()
        source_routine_id = str(item.get("source_routine_id") or "").strip().lower()
        tags = {str(tag).strip().lower() for tag in self._dict_list(item, "tags")}
        if record_id in {"mcp-task", "mcp-routine", "smoke-task", "smoke-idea", "smoke-routine"}:
            return True
        if source_routine_id in {"mcp-routine", "smoke-routine"}:
            return True
        if title in {"mcp task", "mcp routine", "test idea", "smoke task", "smoke idea"}:
            return True
        return "smoke" in tags and any(token in title for token in ("smoke", "test", "mcp"))
