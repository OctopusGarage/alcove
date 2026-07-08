from __future__ import annotations

import json
from pathlib import Path
import re
import shutil

from alcove.inbox_models import InboxNoteRequest, InboxPost, InboxProcessResult
from alcove.inbox_workflow import InboxPromotionWorkflow
from alcove.knowledge import KnowledgeModule
from alcove.markdown import normalize_slug
from alcove.workspace import Workspace


PLATFORM_READ_ORDER = {
    "wechat": ("article.md", "post.md", "ocr-merge.txt"),
    "xhs": ("summary.md", "ocr-merge.txt", "post.md"),
    "x": ("post.md", "ocr-merge.txt", "summary.md"),
    "web": ("article.md", "summary.md", "post.md"),
    "manual": ("note.md", "post.md", "summary.md"),
    "fallback": ("post.md", "summary.md", "article.md", "ocr-merge.txt"),
}


class InboxModule:
    def __init__(self, workspace: Workspace, knowledge: KnowledgeModule | None = None) -> None:
        self.workspace = workspace
        self.paths = workspace.paths()
        self.knowledge = knowledge or KnowledgeModule(workspace)

    def peek(self) -> InboxPost | None:
        entries = self._entries()
        if not entries:
            return None
        return self._read_path(entries[0])

    def read(self, name: str) -> InboxPost:
        return self._read_path(self._find_entry(name))

    def add_manual(
        self,
        title: str,
        content: str,
        source: str = "",
    ) -> dict:
        slug = normalize_slug(title)
        if not slug:
            raise ValueError("Manual inbox title cannot be empty")
        dest = self._unique_folder_path(self.paths.inbox / "manual" / slug)
        dest.mkdir(parents=True, exist_ok=True)
        body = [f"# {title.strip()}", ""]
        if source:
            body.extend([f"Source URL: {source.strip()}", ""])
        body.append(content.strip())
        (dest / "note.md").write_text("\n".join(body).rstrip() + "\n", encoding="utf-8")
        return {"status": "added", "path": str(dest), "id": f"manual/{dest.name}"}

    def note(self, request: InboxNoteRequest) -> InboxProcessResult:
        return InboxPromotionWorkflow(self.workspace, self.knowledge).note(
            self.read(request.name),
            request,
        )

    def archive(
        self,
        name: str,
        topic: str,
        summary: str = "",
        tags: list[str] | None = None,
        no_auto_tags: bool = False,
        supersede_similar: bool = False,
    ) -> InboxProcessResult:
        return InboxPromotionWorkflow(self.workspace, self.knowledge).archive(
            self.read(name),
            topic,
            summary=summary,
            tags=tags,
            no_auto_tags=no_auto_tags,
            supersede_similar=supersede_similar,
        )

    def todo(self, name: str, reason: str = "") -> Path:
        post = self.read(name)
        dest = self._unique_folder_path(self.paths.todo / post.name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(post.path), str(dest))
        if reason:
            (dest / "todo.md").write_text(f"# 待处理\n\n{reason}\n", encoding="utf-8")
        return dest

    def delete(self, name: str, confirm: bool = False) -> dict:
        post = self.read(name)
        if not confirm:
            return {
                "status": "preview",
                "path": str(post.path),
                "confirm_required": True,
            }
        shutil.rmtree(post.path)
        return {"status": "deleted", "path": str(post.path)}

    def _entries(self) -> list[Path]:
        entries: list[Path] = []
        if not self.paths.inbox.exists():
            return entries
        for platform_dir in sorted(self.paths.inbox.iterdir(), key=lambda p: p.name):
            if not platform_dir.is_dir():
                continue
            for item in platform_dir.iterdir():
                if item.is_dir():
                    entries.append(item)
        return sorted(entries, key=lambda p: self._sort_key(p.name))

    def _sort_key(self, name: str) -> tuple[str, str]:
        match = re.match(r"^(\d{8})(?!\d)", name)
        return (match.group(1) if match else "99999999", name)

    def _find_entry(self, name: str) -> Path:
        platform, item_name = self._parse_identifier(name)
        if platform is not None:
            entry = self.paths.inbox / platform / item_name
            if entry.is_dir():
                return entry
            raise FileNotFoundError(f"Inbox item not found: {name}")

        matches = [entry for entry in self._entries() if entry.name == item_name]
        if not matches:
            raise FileNotFoundError(f"Inbox item not found: {name}")
        if len(matches) > 1:
            identifiers = ", ".join(f"{entry.parent.name}/{entry.name}" for entry in matches)
            raise ValueError(
                f"Ambiguous inbox item {name!r}; use platform/name. Matches: {identifiers}"
            )
        return matches[0]

    def _parse_identifier(self, name: str) -> tuple[str | None, str]:
        identifier = str(name)
        if Path(identifier).is_absolute():
            raise ValueError(f"Invalid inbox identifier {name!r}")

        parts = identifier.split("/")
        if len(parts) == 1:
            item_name = parts[0]
            if self._invalid_identifier_component(item_name):
                raise ValueError(f"Invalid inbox identifier {name!r}")
            return None, item_name

        if len(parts) != 2:
            raise ValueError(f"Invalid inbox identifier {name!r}")

        platform, item_name = parts
        if self._invalid_identifier_component(platform) or self._invalid_identifier_component(
            item_name
        ):
            raise ValueError(f"Invalid inbox identifier {name!r}")
        return platform, item_name

    def _invalid_identifier_component(self, value: str) -> bool:
        return value in {"", ".", ".."} or "/" in value

    def _read_path(self, path: Path) -> InboxPost:
        platform = path.parent.name
        metadata = self._capture_metadata(path)
        candidates = PLATFORM_READ_ORDER.get(platform, PLATFORM_READ_ORDER["fallback"])
        content_path = next((path / name for name in candidates if (path / name).is_file()), None)
        if content_path is None:
            raise FileNotFoundError(f"No readable content file found in {path}")
        content = content_path.read_text(encoding="utf-8")
        title = self._title_from_content_or_metadata(content, metadata, path.name)
        source = self._extract_source(content) or self._metadata_string(
            metadata, "source_url", "canonical_url"
        )
        date = self._date_from_name(path.name) or self._metadata_date(metadata)
        return InboxPost(path.name, path, platform, title, source, date, content, content_path.name)

    def _capture_metadata(self, path: Path) -> dict:
        metadata_path = path / "capture.json"
        if not metadata_path.is_file():
            return {}
        try:
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _first_heading(self, content: str) -> str:
        for line in content.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return ""

    def _title_from_content_or_metadata(self, content: str, metadata: dict, fallback: str) -> str:
        heading = self._first_heading(content)
        metadata_title = self._metadata_string(metadata, "title")
        if heading and heading.lower() not in {"summary", "article", "post", "content"}:
            return heading
        return metadata_title or heading or fallback

    def _metadata_string(self, metadata: dict, *keys: str) -> str | None:
        for key in keys:
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _metadata_date(self, metadata: dict) -> str | None:
        for key in ("published_at", "captured_at"):
            value = self._metadata_string(metadata, key)
            if value and re.match(r"^\d{4}-\d{2}-\d{2}", value):
                return value[:10]
        return None

    def _extract_source(self, content: str) -> str | None:
        for line in content.splitlines():
            stripped = line.strip()
            match = re.search(r"(?:Source URL:|来源[:：])\s*(\S+)", stripped)
            if match:
                return match.group(1).strip()
        match = re.search(r"https?://\S+", content)
        return match.group(0) if match else None

    def _date_from_name(self, name: str) -> str | None:
        match = re.match(r"^(\d{4})(\d{2})(\d{2})(?!\d)", name)
        if not match:
            return None
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

    def _unique_folder_path(self, path: Path) -> Path:
        dest = path
        counter = 2
        original = path
        while dest.exists():
            dest = Path(f"{original}-{counter}")
            counter += 1
        return dest
