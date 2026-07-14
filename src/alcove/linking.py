from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex
from typing import Any

from alcove.external_resolver import ExternalItemResolver
from alcove.home import AlcoveHome
from alcove.knowledge import KnowledgeModule, NoteSourceRequest
from alcove.markdown import MarkdownRepository
from alcove.paths import compact_user_path
from alcove.runtime import AlcoveRuntime
from alcove.search import SearchModule, SearchRequest
from alcove.search_rows import SearchRowBuilder
from alcove.workspace import Workspace


@dataclass(frozen=True)
class LinkSourceRequest:
    item_path: str
    topic: str
    summary: str = ""
    create_concept: bool = False


class LinkingModule:
    def __init__(self, workspace: Workspace, home: AlcoveHome | None = None) -> None:
        self.workspace = workspace
        self.home = home
        self.runtime = AlcoveRuntime.from_modules(workspace=workspace, home=home)
        self.rows = SearchRowBuilder(self.runtime.knowledge_root)
        self.external_resolver = ExternalItemResolver(self.runtime)

    def link_source(self, request: LinkSourceRequest) -> dict[str, Any]:
        row = self._find_row(request.item_path)
        result = KnowledgeModule(self.workspace).note_source(
            NoteSourceRequest(
                platform=self._platform(row),
                title=str(row.get("title") or request.item_path),
                topic=request.topic,
                resource=str(row.get("resource") or ""),
                summary=self._source_summary(row, request.summary),
                tags=[str(tag) for tag in row.get("tags") or []],
                legacy_path=request.item_path,
                create_concept=request.create_concept,
                confidence=self._confidence(row),
            )
        )
        source_doc = MarkdownRepository().read_doc(result.source_path)
        notes_excerpt, notes_excerpt_truncated, notes_excerpt_omitted_chars = self._notes_excerpt(
            source_doc.body
        )
        source_relative_path = self._source_relative_path(result.source_path)
        workspace_command_path = compact_user_path(self.workspace.root)
        read_command = (
            f"cd {self._shell_path(workspace_command_path)} && "
            f"cat {shlex.quote(source_relative_path)}"
        )
        return {
            "workspace": str(self.workspace.root),
            "status": "linked",
            "item_path": request.item_path,
            "source_path": str(result.source_path),
            "source_relative_path": source_relative_path,
            "concept_path": str(result.concept_path) if result.concept_path else "",
            "concept_status": "created" if result.concept_path else "source_only",
            "concept_reason": (
                "Knowledge Concept created."
                if result.concept_path
                else "Source-only promotion; pass create_concept=True to also synthesize a Knowledge Concept."
            ),
            "source": {
                "title": str(source_doc.frontmatter.get("title") or ""),
                "resource": str(source_doc.frontmatter.get("resource") or ""),
                "tags": source_doc.frontmatter.get("tags") or [],
                "status": str(source_doc.frontmatter.get("status") or ""),
                "confidence": source_doc.frontmatter.get("confidence"),
                "notes_excerpt": notes_excerpt,
                "notes_excerpt_truncated": notes_excerpt_truncated,
                "notes_excerpt_omitted_chars": notes_excerpt_omitted_chars,
                "read_command": read_command,
                "full_source_hint": (
                    "notes_excerpt is a preview; read_command includes the managed KB "
                    "workspace context for the complete OKF Source document."
                ),
            },
            **({"home": str(self.home.root)} if self.home is not None else {}),
        }

    def _shell_path(self, value: str) -> str:
        if value.startswith("~/") and all(char not in value for char in " \t\n'\""):
            return value
        return shlex.quote(value)

    def _find_row(self, item_path: str) -> dict[str, Any]:
        direct = self._find_external_row(item_path)
        if direct is not None:
            return direct
        rows = SearchModule(self.workspace, home=self.home).search(SearchRequest(limit=10000))
        for row in rows:
            if row.get("path") == item_path:
                return row
        raise FileNotFoundError(f"Indexed item not found: {item_path}")

    def _find_external_row(self, item_path: str) -> dict[str, Any] | None:
        try:
            return dict(self.external_resolver.resolve(item_path).search_row(self.rows))
        except (FileNotFoundError, ValueError):
            return None

    def _platform(self, row: dict[str, Any]) -> str:
        platform = str(row.get("platform") or "")
        if platform:
            return platform
        root = str(row.get("root") or "")
        return root or "external"

    def _confidence(self, row: dict[str, Any]) -> float:
        try:
            return round(float(row.get("confidence", 0.5)), 2)
        except (TypeError, ValueError):
            return 0.5

    def _notes_excerpt(self, body: str, max_chars: int = 400) -> tuple[str, bool, int]:
        if len(body) <= max_chars:
            return body, False, 0
        return body[:max_chars], True, len(body) - max_chars

    def _shell_read_path(self, path: Path | str) -> str:
        public_path = compact_user_path(path)
        if public_path.startswith("~/"):
            return '"$HOME/' + self._escape_double_quoted_shell(public_path[2:]) + '"'
        return shlex.quote(public_path)

    def _source_relative_path(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.workspace.root.resolve()).as_posix()
        except (OSError, ValueError):
            return compact_user_path(path)

    def _escape_double_quoted_shell(self, value: str) -> str:
        return (
            value.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")
        )

    def _source_summary(self, row: dict[str, Any], summary: str) -> str:
        parts = [summary.strip()] if summary.strip() else []
        notes = str(row.get("notes") or "").strip()
        if notes and notes not in parts:
            parts.append(notes)
        details = self._source_details(row)
        if details:
            parts.append("## Connector Context\n\n" + "\n".join(details))
        return "\n\n".join(parts) or str(row.get("title") or "")

    def _source_details(self, row: dict[str, Any]) -> list[str]:
        details: list[str] = []
        field_labels = [
            ("type", "Type"),
            ("platform", "Platform"),
            ("domain", "Account"),
            ("topic", "Language" if row.get("platform") == "github-stars" else "Folder"),
            ("stars", "Stars"),
            ("updated_at", "Updated"),
            ("connector_name", "Connector"),
            ("status", "Status"),
            ("resource", "Resource"),
        ]
        for field, label in field_labels:
            value = row.get(field)
            if value not in (None, ""):
                details.append(f"- {label}: {value}")
        tags = row.get("tags")
        if isinstance(tags, list) and tags:
            details.append("- Tags: " + ", ".join(str(tag) for tag in tags))
        return details
