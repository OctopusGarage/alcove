from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from alcove.dashboard_time import dashboard_time_iso
from alcove.home import AlcoveHome
from alcove.pins import PinsModule
from alcove.projects import ProjectsModule
from alcove.prompts import PromptsModule


class DashboardActivityRows:
    """Dashboard activity feed rows from usage logs and home data changes."""

    def __init__(self, home: AlcoveHome) -> None:
        self.home = home

    def rows(self) -> list[dict[str, Any]]:
        paths: list[Path] = []
        for pattern in [
            "pins/*.md",
            "pins/imports/*.json",
            "prompts/*.md",
            "tasks/*.json",
            "projects/*.json",
            "mounts/**/*.json",
            "connectors/*/index.json",
            "knowledge-bases/*.yml",
        ]:
            paths.extend(self.home.root.glob(pattern))
        rows = self.event_rows()
        event_times_by_area = self.event_times_by_area(rows)
        for path in paths:
            if not path.is_file():
                continue
            area = path.relative_to(self.home.root).parts[0]
            if self.skip_activity_path(path):
                continue
            raw_updated_at = datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(
                timespec="seconds"
            )
            if self.is_derived_activity_update(area, raw_updated_at, event_times_by_area):
                continue
            rows.append(
                {
                    "type": "update",
                    "name": self.activity_name(path),
                    "area": area,
                    "detail": self.activity_detail(path),
                    "updated_at": dashboard_time_iso(raw_updated_at),
                    "raw_updated_at": raw_updated_at,
                }
            )
        return sorted(rows, key=lambda row: str(row["updated_at"]), reverse=True)[:24]

    def skip_activity_path(self, path: Path) -> bool:
        relative = path.relative_to(self.home.root)
        if relative.parts[0] == "pins" and len(relative.parts) == 2 and path.suffix == ".md":
            if path.stem == "index":
                return True
            try:
                pin = PinsModule(home=self.home).get(path.stem)
            except FileNotFoundError:
                return True
            if "source-markdown-pin" in pin.tags:
                return True
            return pin.status != "active"
        if (
            relative.parts[0] == "pins"
            and len(relative.parts) > 1
            and relative.parts[1] == "imports"
        ):
            return True
        if relative.parts[0] in {"connectors", "mounts"}:
            return True
        return False

    def event_times_by_area(self, rows: list[dict[str, Any]]) -> dict[str, list[datetime]]:
        event_times: dict[str, list[datetime]] = {}
        for row in rows:
            if row.get("type") != "action":
                continue
            area = str(row.get("area") or "")
            raw_updated_at = str(row.get("raw_updated_at") or "")
            try:
                event_time = datetime.fromisoformat(raw_updated_at)
            except ValueError:
                continue
            event_times.setdefault(area, []).append(event_time)
        return event_times

    def is_derived_activity_update(
        self,
        file_area: str,
        raw_updated_at: str,
        event_times_by_area: dict[str, list[datetime]],
    ) -> bool:
        event_area = {
            "pins": "pin",
            "prompts": "prompt",
            "projects": "project",
            "tasks": "task",
        }.get(file_area)
        if not event_area:
            return False
        try:
            file_time = datetime.fromisoformat(raw_updated_at)
        except ValueError:
            return False
        return any(
            abs((file_time - event_time).total_seconds()) <= 300
            for event_time in event_times_by_area.get(event_area, [])
        )

    def activity_name(self, path: Path) -> str:
        relative = path.relative_to(self.home.root)
        area = relative.parts[0]
        if area == "pins":
            if len(relative.parts) > 1 and relative.parts[1] == "imports":
                return "Imported pin source saved"
            return "Pin updated"
        if area == "connectors":
            return (
                f"{relative.parts[1]} connector refreshed"
                if len(relative.parts) > 1
                else "Connector refreshed"
            )
        if area == "mounts":
            return "Mount refreshed"
        if area == "tasks":
            return "Planner updated"
        if area == "prompts":
            return "Prompt saved"
        if area == "projects":
            return "Project shortcut updated"
        if area == "knowledge-bases":
            return "Knowledge base changed"
        return f"{area} updated"

    def activity_detail(self, path: Path) -> str:
        relative = path.relative_to(self.home.root)
        if relative.parts[0] == "pins" and path.suffix == ".md":
            try:
                pin = PinsModule(home=self.home).get(path.stem)
            except FileNotFoundError:
                return "Pin record changed"
            return pin.title
        if relative.parts[0] == "connectors" and len(relative.parts) > 1:
            return f"{relative.parts[1]} local search index"
        if relative.parts[0] == "mounts":
            return path.stem
        if relative.parts[0] == "tasks":
            return self.planner_activity_detail(path)
        if relative.parts[0] == "prompts" and path.suffix == ".md":
            try:
                prompt = PromptsModule(home=self.home).get(path.stem)
            except FileNotFoundError:
                return path.stem
            return prompt.title
        if relative.parts[0] == "projects":
            try:
                projects = ProjectsModule(home=self.home).list()
            except (FileNotFoundError, json.JSONDecodeError):
                return path.stem
            aliases = [project.alias for project in projects[:5]]
            return ", ".join(aliases) if aliases else path.stem
        return path.stem

    def planner_activity_detail(self, path: Path) -> str:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return path.stem
        parts: list[str] = []
        for key, label in [
            ("tasks", "tasks"),
            ("ideas", "ideas"),
            ("routines", "routines"),
        ]:
            values = data.get(key)
            if isinstance(values, dict):
                records = list(values.items())[:3]
            elif isinstance(values, list):
                records = [
                    (str(index), item)
                    for index, item in enumerate(values[:3])
                    if isinstance(item, dict)
                ]
            else:
                continue
            titles = [
                str(item.get("title") or item_id)
                for item_id, item in records
                if isinstance(item, dict)
            ]
            if titles:
                parts.append(f"{label}: {', '.join(titles)}")
        return "; ".join(parts) if parts else path.stem

    def event_rows(self) -> list[dict[str, Any]]:
        log_path = self.home.paths().logs / "activity.jsonl"
        if not log_path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line in log_path.read_text(encoding="utf-8").splitlines()[-100:]:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("action") in {
                "dashboard.build",
                "dashboard.route",
                "dashboard.search",
            }:
                continue
            if event.get("action") == "knowledge.delete":
                raw_metadata = event.get("metadata")
                metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
                if str(metadata.get("confirmed") or "").casefold() != "true":
                    continue
            if not event.get("visible", True):
                continue
            raw_updated_at = str(event.get("updated_at") or "")
            rows.append(
                {
                    "type": "action",
                    "name": self.event_name(event),
                    "area": str(event.get("area") or "activity"),
                    "detail": self.event_detail(event),
                    "updated_at": dashboard_time_iso(raw_updated_at),
                    "raw_updated_at": raw_updated_at,
                }
            )
        return rows

    def event_name(self, event: dict[str, Any]) -> str:
        action = str(event.get("action") or "")
        raw_metadata = event.get("metadata")
        metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
        title = str(metadata.get("title") or "").strip()
        if action == "knowledge.delete" and title:
            return f"Deleted knowledge: {title}"
        if action == "knowledge.revise" and title:
            return f"Revised knowledge: {title}"
        return str(event.get("summary") or action or "event")

    def event_detail(self, event: dict[str, Any]) -> str:
        action = str(event.get("action") or "")
        raw_metadata = event.get("metadata")
        metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
        if action == "dashboard.import_pins":
            regular = metadata.get("regular")
            todo = metadata.get("todo")
            regular_count = regular.get("imported", 0) if isinstance(regular, dict) else 0
            todo_count = todo.get("imported", 0) if isinstance(todo, dict) else 0
            return f"{regular_count} regular themes, {todo_count} todo themes"
        if action in {"knowledge.delete", "knowledge.revise"}:
            path = str(metadata.get("path") or "").strip()
            return path or str(event.get("summary") or action or "event")
        return str(event.get("summary") or action or "event")
