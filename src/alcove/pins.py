from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from alcove.home import AlcoveHome
from alcove.markdown import MarkdownDoc, MarkdownRepository, normalize_slug
from alcove.taxonomy import load_taxonomy, normalize_tag
from alcove.workspace import Workspace


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class AddPinRequest:
    title: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    priority: str = "medium"
    source_refs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Pin:
    id: str
    title: str
    description: str
    tags: list[str]
    status: str
    priority: str
    source_refs: list[str]
    path: Path


@dataclass(frozen=True)
class PinResult:
    path: Path
    pin: Pin


class PinsModule:
    def __init__(
        self,
        workspace: Workspace | None = None,
        repo: MarkdownRepository | None = None,
        home: AlcoveHome | None = None,
    ) -> None:
        self.workspace = workspace
        self.home = home
        if home is None and workspace is None:
            home = AlcoveHome.init()
            self.home = home
        self.pin_root = home.paths().pins if home is not None else workspace.paths().pins
        self.repo = repo or MarkdownRepository()
        self.taxonomy = (
            load_taxonomy(workspace.paths().knowledge)
            if workspace
            else load_taxonomy(self.pin_root)
        )

    def add(self, request: AddPinRequest) -> PinResult:
        path = self.repo.unique_path(self.pin_root, request.title)
        timestamp = now_iso()
        tags = self._normalize_tags(request.tags)
        source_refs = self._normalize_refs(request.source_refs)
        doc = MarkdownDoc(
            frontmatter={
                "type": "Pin",
                "title": request.title,
                "description": request.description,
                "tags": tags,
                "status": "active",
                "priority": self._priority(request.priority),
                "source_refs": source_refs,
                "created_at": timestamp,
                "updated_at": timestamp,
            },
            body=f"# {request.title}\n\n{request.description}\n",
        )
        self.repo.write_doc(path, doc)
        return PinResult(path=path, pin=self._pin_from_doc(self.repo.read_doc(path)))

    def list(self, tag: str | None = None, status: str = "active") -> list[Pin]:
        tag_filter = normalize_tag(tag, self.taxonomy) if tag else None
        pins: list[Pin] = []
        for doc in self.repo.list_docs(self.pin_root, type_filter="Pin"):
            pin = self._pin_from_doc(doc)
            if status and pin.status != status:
                continue
            if tag_filter and tag_filter not in pin.tags:
                continue
            pins.append(pin)
        return pins

    def archive(self, pin_id: str, confirm: bool = False) -> dict:
        doc = self._read_pin(pin_id)
        path = self._doc_path(doc)
        if not confirm:
            return {
                "status": "preview",
                "path": str(path),
                "confirm_required": True,
            }
        frontmatter = {
            **doc.frontmatter,
            "status": "archived",
            "updated_at": now_iso(),
        }
        self.repo.write_doc(path, MarkdownDoc(frontmatter, doc.body))
        return {"status": "archived", "path": str(path)}

    def _read_pin(self, pin_id: str) -> MarkdownDoc:
        slug = normalize_slug(pin_id)
        path = self.pin_root / f"{slug}.md"
        if path.is_file():
            return self.repo.read_doc(path)
        matches = sorted(self.pin_root.glob(f"{slug}-*.md"))
        if matches:
            return self.repo.read_doc(matches[0])
        raise FileNotFoundError(f"Pin not found: {pin_id}")

    def _pin_from_doc(self, doc: MarkdownDoc) -> Pin:
        path = self._doc_path(doc)
        frontmatter = doc.frontmatter
        return Pin(
            id=path.stem,
            title=str(frontmatter.get("title") or path.stem),
            description=str(frontmatter.get("description") or ""),
            tags=self._as_list(frontmatter.get("tags")),
            status=str(frontmatter.get("status") or "active"),
            priority=str(frontmatter.get("priority") or "medium"),
            source_refs=self._as_list(frontmatter.get("source_refs")),
            path=path,
        )

    def _doc_path(self, doc: MarkdownDoc) -> Path:
        if doc.path is None:
            raise ValueError("Pin document has no path")
        return doc.path

    def _normalize_tags(self, tags: list[str]) -> list[str]:
        normalized = {normalize_tag(tag, self.taxonomy) for tag in tags}
        return sorted(tag for tag in normalized if tag)

    def _normalize_refs(self, refs: list[str]) -> list[str]:
        values: list[str] = []
        for ref in refs:
            value = str(ref or "").strip()
            if value and not value.startswith("/"):
                value = f"/{value}"
            if value and value not in values:
                values.append(value)
        return values

    def _priority(self, value: str) -> str:
        priority = normalize_slug(value)
        return priority if priority in {"high", "medium", "low"} else "medium"

    def _as_list(self, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item]
        if value:
            return [str(value)]
        return []
