from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from alcove.dashboard_search_index import build_dashboard_search_index
from alcove.dashboard_data_sources import DashboardDataSources
from alcove.dashboard_projection import DashboardProjection
from alcove.mounts import MountsModule
from alcove.paths import compact_user_path
from alcove.pins import PinsModule
from alcove.projects import ProjectsModule
from alcove.prompts import PromptsModule
from alcove.radars import RadarModule
from alcove.tasks import TasksModule


@dataclass(frozen=True)
class DashboardSnapshotFacts:
    pins: list[Any]
    pending_tasks: list[Any]
    active_ideas: list[Any]
    active_routines: list[Any]
    all_tasks: list[Any]
    all_ideas: list[Any]
    all_routines: list[Any]
    prompt_rows: list[Any]
    project_rows: list[Any]
    mount_rows: list[Any]
    mount_items: list[dict[str, Any]]
    connector_rows: list[dict[str, Any]]
    radar_rows: list[dict[str, Any]]
    blog_rows: list[dict[str, Any]]
    kb_rows: list[Any]
    knowledge_rows: list[dict[str, Any]]
    usage_summary: dict[str, Any]
    active_pins: list[Any]
    direct_pending_tasks: list[Any]
    routine_due_tasks: list[Any]
    theme_pins: list[Any]
    dashboard_pins: list[Any]
    activity: list[dict[str, Any]]


class DashboardSnapshotBuilder:
    """Private dashboard snapshot assembly module.

    DashboardModule owns the public interface and file/build concerns. This module owns the
    cross-module snapshot projection so count and row assembly can be tested and evolved locally.
    """

    def __init__(self, dashboard: Any) -> None:
        self.dashboard = dashboard
        self.home = dashboard.home
        self.data_sources = DashboardDataSources(self.home)
        self.projection = DashboardProjection(self.home)

    def snapshot(self) -> dict[str, Any]:
        facts = self._collect_facts()
        counts = self._counts(facts)
        mount_snapshot_rows = [
            self.data_sources.mount_row(mount, facts.mount_items) for mount in facts.mount_rows
        ]
        health = self.projection.health_summary(
            knowledge_rows=facts.knowledge_rows,
            connector_rows=facts.connector_rows,
            mount_rows=mount_snapshot_rows,
            usage_summary=facts.usage_summary,
        )
        snapshot = {
            "snapshot_version": self.dashboard.snapshot_version,
            "generated_at": self.dashboard.now_iso(),
            "home": self.dashboard._home_label(),
            "summary": {
                "title": "Alcove Dashboard",
                "subtitle": "Local-first personal knowledge workbench",
                "counts": counts,
            },
            "modules": self.projection.modules(counts),
            "pins": {
                "themes": [self.projection.theme_pin_dict(pin) for pin in facts.dashboard_pins],
                "displayed": [self.projection.pin_dict(pin) for pin in facts.dashboard_pins],
                "active": [self.projection.pin_dict(pin) for pin in facts.active_pins],
                "all": [self.projection.pin_dict(pin) for pin in facts.active_pins],
            },
            "tasks": {
                "pending": [self.projection.task_dict(task) for task in facts.pending_tasks],
                "ideas": [asdict(idea) for idea in facts.active_ideas],
                "routines": [asdict(routine) for routine in facts.active_routines],
                "all": [self.projection.task_dict(task) for task in facts.all_tasks],
                "ideas_all": [asdict(idea) for idea in facts.all_ideas],
                "routines_all": [asdict(routine) for routine in facts.all_routines],
            },
            "ideas": [asdict(idea) for idea in facts.all_ideas],
            "routines": [asdict(routine) for routine in facts.active_routines],
            "routines_all": [asdict(routine) for routine in facts.all_routines],
            "knowledge_bases": [
                {
                    "name": row["name"],
                    "item_count": row["item_count"],
                    "inbox_count": row["inbox_count"],
                    "archive_count": row["archive_count"],
                    "updated_at": row["updated_at"],
                }
                for row in facts.knowledge_rows
            ],
            "knowledge": {"managed": facts.knowledge_rows},
            "connectors": facts.connector_rows,
            "mounts": mount_snapshot_rows,
            "radars": facts.radar_rows,
            "blog_monitor": {"sources": facts.blog_rows},
            "sources": {
                "connectors": facts.connector_rows,
                "mounts": mount_snapshot_rows,
                "blogs": facts.blog_rows,
            },
            "prompts": [
                {
                    "id": prompt.id,
                    "title": prompt.title,
                    "description": prompt.description,
                    "content": prompt.content,
                    "kind": prompt.kind,
                    "domain": prompt.domain,
                    "intent": prompt.intent,
                    "surfaces": prompt.surfaces,
                    "triggers": prompt.triggers,
                    "inputs": prompt.inputs,
                    "outputs": prompt.outputs,
                    "quality": prompt.quality,
                    "tags": prompt.tags,
                    "use_cases": prompt.use_cases,
                    "source_refs": prompt.source_refs,
                    "status": prompt.status,
                }
                for prompt in facts.prompt_rows
            ],
            "projects": [
                {
                    "alias": project.alias,
                    "note": project.note,
                    "exists": project.exists,
                    "path_label": Path(project.path).expanduser().name
                    or compact_user_path(project.path),
                    "target_label": (
                        f"{project.alias} "
                        f"({Path(project.path).expanduser().name or compact_user_path(project.path)})"
                    ),
                    "command_hint": f"alcove project get {project.alias} --json",
                    "source": project.source,
                }
                for project in facts.project_rows
            ],
            "activity": facts.activity,
            "usage": facts.usage_summary,
            "health": health,
        }
        snapshot["search_index"] = build_dashboard_search_index(snapshot)
        return snapshot

    def _collect_facts(self) -> DashboardSnapshotFacts:
        pins = PinsModule(home=self.home).list(status="")
        tasks = TasksModule(home=self.home)
        mounts = MountsModule(home=self.home)
        prompts = PromptsModule(home=self.home)
        projects = ProjectsModule(home=self.home)
        pending_tasks = tasks.task_list(status="pending")
        active_ideas = tasks.idea_list(status="active")
        active_routines = tasks.routine_list(status="active")
        all_tasks = tasks.task_list(status="")
        all_ideas = tasks.idea_list(status="")
        all_routines = tasks.routine_list(status="")
        prompt_rows = prompts.list(status="")
        project_rows = projects.list()
        mount_rows = mounts.list(status="")
        mount_items = mounts.index_items()
        connector_rows = self.data_sources.connector_rows()
        radar_rows = RadarModule(self.home).dashboard_rows()
        blog_rows = self.data_sources.blog_rows()
        kb_rows = self.home.list_knowledge_bases()
        knowledge_rows = self.data_sources.knowledge_base_rows(kb_rows)
        usage_summary = self.dashboard._dashboard_usage_summary()
        active_pins = [pin for pin in pins if pin.status == "active"]
        direct_pending_tasks = [
            task for task in pending_tasks if not str(task.source_routine_id or "")
        ]
        routine_due_tasks = [task for task in pending_tasks if str(task.source_routine_id or "")]
        theme_pins = [
            pin
            for pin in active_pins
            if "theme-pin" in pin.tags or "source-markdown-pin" in pin.tags
        ]
        dashboard_pins = theme_pins or active_pins
        activity = self.data_sources.activity_rows()
        return DashboardSnapshotFacts(
            pins=pins,
            pending_tasks=pending_tasks,
            active_ideas=active_ideas,
            active_routines=active_routines,
            all_tasks=all_tasks,
            all_ideas=all_ideas,
            all_routines=all_routines,
            prompt_rows=prompt_rows,
            project_rows=project_rows,
            mount_rows=mount_rows,
            mount_items=mount_items,
            connector_rows=connector_rows,
            radar_rows=radar_rows,
            blog_rows=blog_rows,
            kb_rows=kb_rows,
            knowledge_rows=knowledge_rows,
            usage_summary=usage_summary,
            active_pins=active_pins,
            direct_pending_tasks=direct_pending_tasks,
            routine_due_tasks=routine_due_tasks,
            theme_pins=theme_pins,
            dashboard_pins=dashboard_pins,
            activity=activity,
        )

    def _counts(self, facts: DashboardSnapshotFacts) -> dict[str, int]:
        return {
            "pins": len(facts.active_pins),
            "pin_collections": len(facts.dashboard_pins),
            "theme_pins": len(facts.theme_pins),
            "regular_theme_pins": len(
                [pin for pin in facts.dashboard_pins if pin.kind == "regular"]
            ),
            "todo_theme_pins": len([pin for pin in facts.dashboard_pins if pin.kind == "todo"]),
            "pending_tasks": len(facts.pending_tasks),
            "direct_pending_tasks": len(facts.direct_pending_tasks),
            "routine_due_tasks": len(facts.routine_due_tasks),
            "active_ideas": len(facts.active_ideas),
            "active_routines": len(facts.active_routines),
            "tasks_total": len(facts.all_tasks),
            "ideas_total": len(facts.all_ideas),
            "routines_total": len(facts.all_routines),
            "prompts": len([prompt for prompt in facts.prompt_rows if prompt.status == "active"]),
            "projects": len(facts.project_rows),
            "mounts": len([mount for mount in facts.mount_rows if mount.status == "active"]),
            "mount_items": len(facts.mount_items),
            "connectors": len(facts.connector_rows),
            "connector_items": sum(row["count"] for row in facts.connector_rows),
            "radars": len(facts.radar_rows),
            "radars_current": len([row for row in facts.radar_rows if row["status"] == "current"]),
            "radars_configured": len(
                [row for row in facts.radar_rows if row.get("definition_status") == "active"]
            ),
            "radars_stale": len([row for row in facts.radar_rows if row["status"] == "stale"]),
            "blog_sources": len(facts.blog_rows),
            "blog_sources_active": len(
                [row for row in facts.blog_rows if row["status"] == "active"]
            ),
            "knowledge_bases": len(facts.kb_rows),
            "knowledge_items": sum(row["item_count"] for row in facts.knowledge_rows),
            "activity_events": len(facts.activity),
            "usage_events": facts.usage_summary["total_events"],
        }
