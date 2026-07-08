from __future__ import annotations

from dataclasses import dataclass

from alcove.external_index import ExternalIndexStore, ExternalItemReference
from alcove.home import AlcoveHome
from alcove.knowledge import KnowledgeModule, NoteSourceRequest
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

    def link_source(self, request: LinkSourceRequest) -> dict:
        row = self._find_row(request.item_path)
        result = KnowledgeModule(self.workspace).note_source(
            NoteSourceRequest(
                platform=self._platform(row),
                title=str(row.get("title") or request.item_path),
                topic=request.topic,
                resource=str(row.get("resource") or ""),
                summary=request.summary or str(row.get("notes") or ""),
                tags=[str(tag) for tag in row.get("tags") or []],
                legacy_path=request.item_path,
                create_concept=request.create_concept,
            )
        )
        return {
            "workspace": str(self.workspace.root),
            "status": "linked",
            "item_path": request.item_path,
            "source_path": str(result.source_path),
            "concept_path": str(result.concept_path) if result.concept_path else "",
            **({"home": str(self.home.root)} if self.home is not None else {}),
        }

    def _find_row(self, item_path: str) -> dict:
        direct = self._find_external_row(item_path)
        if direct is not None:
            return direct
        rows = SearchModule(self.workspace, home=self.home).search(SearchRequest(limit=10000))
        for row in rows:
            if row.get("path") == item_path:
                return row
        raise FileNotFoundError(f"Indexed item not found: {item_path}")

    def _find_external_row(self, item_path: str) -> dict | None:
        ref = ExternalItemReference.parse_optional(item_path)
        if ref is None:
            return None
        if ref.kind == "connector":
            item = ExternalIndexStore(self.runtime.connectors_root).find_item(ref)
            if item is None:
                return None
            return self.rows.connector_item(ref.source_id, item)
        if ref.kind == "mount":
            item = ExternalIndexStore(self.runtime.mounts_root).find_item(ref)
            if item is None:
                return None
            return self.rows.mount_item(item)
        return None

    def _platform(self, row: dict) -> str:
        platform = str(row.get("platform") or "")
        if platform:
            return platform
        root = str(row.get("root") or "")
        return root or "external"
