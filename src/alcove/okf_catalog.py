from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from alcove.home import AlcoveHome
from alcove.markdown import MarkdownDoc, MarkdownRepository
from alcove.mounts import MountsModule
from alcove.paths import compact_user_path
from alcove.pins import PinsModule
from alcove.projects import ProjectsModule
from alcove.prompts import PromptsModule
from alcove.tasks import TasksModule


CATALOG_FILES = [
    "index.md",
    "log.md",
    "managed-kbs.md",
    "global-memory.md",
    "external-indexes.md",
    "search-map.md",
    "modules/pins.md",
    "modules/prompts.md",
    "modules/tasks.md",
    "modules/projects.md",
    "modules/mounts.md",
    "modules/connectors.md",
]


class OkfCatalogModule:
    """Build the derived global OKF entry point for AI-led reads."""

    def __init__(self, home: AlcoveHome) -> None:
        self.home = home
        self.root = home.paths().okf

    def build(self) -> dict[str, Any]:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "modules").mkdir(parents=True, exist_ok=True)

        context = self._context()
        self._write("index.md", self._index_body(context))
        self._write("managed-kbs.md", self._managed_kbs_body(context["managed_kbs"]))
        self._write("global-memory.md", self._global_memory_body(context))
        self._write("external-indexes.md", self._external_indexes_body(context))
        self._write("search-map.md", self._search_map_body())
        self._write("modules/pins.md", self._pins_body(context["pins"]))
        self._write("modules/prompts.md", self._prompts_body(context["prompts"]))
        self._write("modules/tasks.md", self._tasks_body(context))
        self._write("modules/projects.md", self._projects_body(context["projects"]))
        self._write("modules/mounts.md", self._mounts_body(context["mounts"]))
        self._write("modules/connectors.md", self._connectors_body(context["connectors"]))
        self._write("log.md", self._log_body())

        files = [path for path in CATALOG_FILES if (self.root / path).is_file()]
        return {
            "status": "built",
            "root": str(self.root),
            "files": files,
            "counts": {
                "managed_kbs": len(context["managed_kbs"]),
                "pins": len(context["pins"]),
                "prompts": len(context["prompts"]),
                "tasks": len(context["tasks"]),
                "ideas": len(context["ideas"]),
                "routines": len(context["routines"]),
                "projects": len(context["projects"]),
                "mounts": len(context["mounts"]),
                "connectors": len(context["connectors"]),
            },
        }

    def _context(self) -> dict[str, Any]:
        tasks = TasksModule(home=self.home)
        return {
            "managed_kbs": self.home.list_knowledge_bases(),
            "pins": PinsModule(home=self.home).list(status="active"),
            "prompts": PromptsModule(home=self.home).list(status="active"),
            "tasks": tasks.task_list(status="pending"),
            "ideas": tasks.idea_list(status="active"),
            "routines": tasks.routine_list(status="active"),
            "projects": ProjectsModule(home=self.home).list(),
            "mounts": MountsModule(home=self.home).list(status="active"),
            "connectors": self._connectors(),
        }

    def _connectors(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        root = self.home.paths().connectors
        if not root.exists():
            return rows
        for index_path in sorted(root.glob("*/index.json"), key=lambda path: path.as_posix()):
            data = self._read_json(index_path)
            connector = str(data.get("connector") or index_path.parent.name)
            items = data.get("items") if isinstance(data.get("items"), list) else []
            rows.append(
                {
                    "connector": connector,
                    "source_id": str(data.get("source_id") or data.get("source") or ""),
                    "count": len([item for item in items if isinstance(item, dict)]),
                    "index_path": index_path,
                    "okf_index": index_path.parent / "okf" / "index.md",
                }
            )
        return rows

    def _index_body(self, context: dict[str, Any]) -> str:
        counts = {
            "managed KBs": len(context["managed_kbs"]),
            "global memory records": len(context["pins"])
            + len(context["prompts"])
            + len(context["tasks"])
            + len(context["ideas"])
            + len(context["routines"])
            + len(context["projects"]),
            "external indexes": len(context["mounts"]) + len(context["connectors"]),
        }
        return "\n".join(
            [
                "# Alcove Global OKF Catalog",
                "",
                "This is a derived progressive-disclosure entry for AI-led reads.",
                "It is not the source of truth. Regenerate it with `alcove okf catalog build`.",
                "",
                "## Sections",
                "",
                "- [Managed Knowledge Bases](managed-kbs.md)",
                "- [Global Memory](global-memory.md)",
                "- [External Indexes](external-indexes.md)",
                "- [Search Map](search-map.md)",
                "",
                "## Counts",
                "",
                *[f"- {label}: {count}" for label, count in counts.items()],
                "",
                "## Module Entrypoints",
                "",
                "- [Pins](modules/pins.md)",
                "- [Prompts](modules/prompts.md)",
                "- [Tasks](modules/tasks.md)",
                "- [Projects](modules/projects.md)",
                "- [Mounts](modules/mounts.md)",
                "- [Connectors](modules/connectors.md)",
                "",
            ]
        )

    def _managed_kbs_body(self, records: list[Any]) -> str:
        lines = [
            "# Managed Knowledge Bases",
            "",
            "Managed KBs are Alcove-governed writable knowledge roots.",
            "",
        ]
        if not records:
            lines.append("- No managed knowledge bases registered.")
        for record in records:
            registry_ref = f"../knowledge-bases/{record.name}.yml"
            lines.append(
                f"- **{record.name}**: `{compact_user_path(record.path)}` "
                f"([registry]({registry_ref}))"
            )
        return "\n".join(lines) + "\n"

    def _global_memory_body(self, context: dict[str, Any]) -> str:
        project_lines = [
            f"- **{project.alias}**: `{compact_user_path(project.path)}`"
            for project in context["projects"]
        ] or ["- No projects."]
        return "\n".join(
            [
                "# Global Memory",
                "",
                "Global memory is stored under Alcove Home and participates in global search.",
                "",
                "## Pins",
                "",
                *self._record_lines(context["pins"], "title", "../pins/{id}.md"),
                "",
                "## Prompts",
                "",
                *self._record_lines(context["prompts"], "title", "../prompts/{id}.md"),
                "",
                "## Tasks",
                "",
                *self._record_lines(context["tasks"], "title", ""),
                "",
                "## Ideas",
                "",
                *self._record_lines(context["ideas"], "title", ""),
                "",
                "## Routines",
                "",
                *self._record_lines(context["routines"], "title", ""),
                "",
                "## Projects",
                "",
                *project_lines,
                "",
            ]
        )

    def _external_indexes_body(self, context: dict[str, Any]) -> str:
        return "\n".join(
            [
                "# External Indexes",
                "",
                "External indexes are read-oriented mirrors over mounted folders and connectors.",
                "",
                "## Mounts",
                "",
                *self._mount_lines(context["mounts"]),
                "",
                "## Connectors",
                "",
                *self._connector_lines(context["connectors"]),
                "",
            ]
        )

    def _search_map_body(self) -> str:
        return "\n".join(
            [
                "# Search Map",
                "",
                "Search returns candidates, not final answers.",
                "",
                "## Read Path",
                "",
                "1. Start with `alcove search` or MCP `alcove_search`.",
                "2. Inspect this catalog, module indexes, and candidate source records.",
                "3. Follow managed KB source refs, connector fetch refs, and mount refs.",
                "4. Use local file reads and shell search when useful.",
                "5. Synthesize from the concrete evidence inspected.",
                "",
                "## Write Path",
                "",
                "Durable writes should go through Alcove CLI/MCP commands. Direct file edits are "
                "repair fallbacks and should be followed by validation or index rebuilds.",
                "",
            ]
        )

    def _pins_body(self, pins: list[Any]) -> str:
        return self._module_body(
            "Pins",
            "Source of truth: `~/.alcove/pins/*.md`.",
            self._record_lines(pins, "title", "../pins/{id}.md"),
        )

    def _prompts_body(self, prompts: list[Any]) -> str:
        return self._module_body(
            "Prompts",
            "Source of truth: `~/.alcove/prompts/*.md`.",
            self._record_lines(prompts, "title", "../prompts/{id}.md"),
        )

    def _tasks_body(self, context: dict[str, Any]) -> str:
        lines = [
            "# Tasks",
            "",
            "Source of truth: `~/.alcove/tasks/tasks.json`.",
            "",
            "## Pending Tasks",
            "",
            *self._record_lines(context["tasks"], "title", ""),
            "",
            "## Active Ideas",
            "",
            *self._record_lines(context["ideas"], "title", ""),
            "",
            "## Active Routines",
            "",
            *self._record_lines(context["routines"], "title", ""),
            "",
        ]
        return "\n".join(lines)

    def _projects_body(self, projects: list[Any]) -> str:
        lines = [
            "# Projects",
            "",
            "Source of truth: `~/.alcove/projects/projects.json`.",
            "",
        ]
        if not projects:
            lines.append("- No projects.")
        for project in projects:
            lines.append(f"- **{project.alias}**: `{compact_user_path(project.path)}`")
        return "\n".join(lines) + "\n"

    def _mounts_body(self, mounts: list[Any]) -> str:
        return self._module_body(
            "Mounts",
            "Source of truth: external folders plus `~/.alcove/mounts/indexes/*.json`.",
            self._mount_lines(mounts),
        )

    def _connectors_body(self, connectors: list[dict[str, Any]]) -> str:
        return self._module_body(
            "Connectors",
            "Source of truth: external systems/exports plus connector indexes.",
            self._connector_lines(connectors),
        )

    def _module_body(self, title: str, intro: str, rows: list[str]) -> str:
        return "\n".join([f"# {title}", "", intro, "", *(rows or ["- No records."]), ""])

    def _record_lines(self, records: list[Any], title_attr: str, link_template: str) -> list[str]:
        rows = []
        for record in records:
            data = asdict(record) if not isinstance(record, dict) else record
            title = str(data.get(title_attr) or data.get("id") or "Untitled")
            record_id = str(data.get("id") or data.get("alias") or "")
            tags = data.get("tags") if isinstance(data.get("tags"), list) else []
            suffix = f" tags: {', '.join(tags)}" if tags else ""
            if link_template and record_id:
                rows.append(f"- [{title}]({link_template.format(id=record_id)}){suffix}")
            else:
                rows.append(f"- **{title}**{suffix}")
        return rows or ["- No records."]

    def _mount_lines(self, mounts: list[Any]) -> list[str]:
        rows = []
        for mount in mounts:
            okf_ref = f"../mounts/okf/{mount.id}/index.md"
            rows.append(
                f"- **{mount.name}** (`{mount.id}`): `{compact_user_path(Path(mount.path))}` "
                f"([okf]({okf_ref}))"
            )
        return rows or ["- No mounts."]

    def _connector_lines(self, connectors: list[dict[str, Any]]) -> list[str]:
        rows = []
        for connector in connectors:
            connector_id = str(connector["connector"])
            okf_ref = f"../connectors/{connector_id}/okf/index.md"
            rows.append(f"- **{connector_id}**: {connector['count']} items ([okf]({okf_ref}))")
        return rows or ["- No connectors."]

    def _log_body(self) -> str:
        today = datetime.now(UTC).date().isoformat()
        return "\n".join(
            [
                "# Alcove OKF Catalog Log",
                "",
                f"## {today}",
                "",
                "- **Update**: Rebuilt derived global OKF catalog.",
                "",
            ]
        )

    def _write(self, relative_path: str, body: str) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        MarkdownRepository().write_doc(
            path,
            MarkdownDoc(
                frontmatter={
                    "type": "Index",
                    "schema": "alcove/global-okf-catalog/v1",
                    "title": self._title_from_body(body, relative_path),
                    "status": "active",
                    "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                },
                body=body,
            ),
        )

    def _title_from_body(self, body: str, fallback: str) -> str:
        for line in body.splitlines():
            if line.startswith("# "):
                return line.removeprefix("# ").strip()
        return fallback

    def _read_json(self, path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}
