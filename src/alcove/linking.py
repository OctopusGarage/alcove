from __future__ import annotations

from dataclasses import dataclass

from alcove.knowledge import KnowledgeModule, NoteSourceRequest
from alcove.search import SearchModule, SearchRequest
from alcove.workspace import Workspace


@dataclass(frozen=True)
class LinkSourceRequest:
    item_path: str
    topic: str
    summary: str = ""
    create_concept: bool = False


class LinkingModule:
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

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
        }

    def _find_row(self, item_path: str) -> dict:
        rows = SearchModule(self.workspace).search(SearchRequest(limit=10000))
        for row in rows:
            if row.get("path") == item_path:
                return row
        raise FileNotFoundError(f"Indexed item not found: {item_path}")

    def _platform(self, row: dict) -> str:
        platform = str(row.get("platform") or "")
        if platform:
            return platform
        root = str(row.get("root") or "")
        return root or "external"
