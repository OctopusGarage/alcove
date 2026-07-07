from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import shutil

from alcove.knowledge import KnowledgeModule, NoteSourceRequest
from alcove.markdown import normalize_slug
from alcove.workspace import Workspace


PLATFORM_READ_ORDER = {
    "wechat": ("article.md", "post.md", "ocr-merge.txt"),
    "xhs": ("summary.md", "ocr-merge.txt", "post.md"),
    "x": ("post.md", "ocr-merge.txt", "summary.md"),
    "web": ("article.md", "summary.md", "post.md"),
    "fallback": ("post.md", "summary.md", "article.md", "ocr-merge.txt"),
}


@dataclass(frozen=True)
class InboxPost:
    name: str
    path: Path
    platform: str
    title: str
    source: str | None
    date: str | None
    content: str
    content_source: str


@dataclass(frozen=True)
class InboxNoteRequest:
    name: str
    topic: str
    summary: str
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class InboxProcessResult:
    archive_path: Path
    source_path: Path
    concept_path: Path | None


class InboxModule:
    def __init__(self, workspace: Workspace, knowledge: KnowledgeModule | None = None) -> None:
        self.workspace = workspace
        self.paths = workspace.paths()
        self.knowledge = knowledge or KnowledgeModule(workspace)

    def peek(self) -> InboxPost | None:
        entries = self._entries()
        if not entries:
            return None
        return self.read(entries[0].name)

    def read(self, name: str) -> InboxPost:
        for entry in self._entries():
            if entry.name == name:
                return self._read_path(entry)
        raise FileNotFoundError(f"Inbox item not found: {name}")

    def note(self, request: InboxNoteRequest) -> InboxProcessResult:
        post = self.read(request.name)
        archive_path = self._archive_post(post, request.topic)
        archive_reference = self._legacy_path(archive_path)
        result = self.knowledge.note_source(
            NoteSourceRequest(
                platform=post.platform,
                title=post.title or post.name,
                topic=request.topic,
                resource=post.source or archive_reference,
                summary=request.summary,
                tags=request.tags,
                published_date=post.date,
                legacy_path=archive_reference,
                create_concept=True,
            )
        )
        return InboxProcessResult(archive_path, result.source_path, result.concept_path)

    def archive(
        self,
        name: str,
        topic: str,
        summary: str = "",
        tags: list[str] | None = None,
    ) -> InboxProcessResult:
        post = self.read(name)
        archive_path = self._archive_post(post, topic)
        archive_reference = self._legacy_path(archive_path)
        result = self.knowledge.note_source(
            NoteSourceRequest(
                platform=post.platform,
                title=post.title or post.name,
                topic=topic,
                resource=post.source or archive_reference,
                summary=summary or post.content,
                tags=tags or [],
                published_date=post.date,
                legacy_path=archive_reference,
                create_concept=False,
            )
        )
        return InboxProcessResult(archive_path, result.source_path, result.concept_path)

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

    def _read_path(self, path: Path) -> InboxPost:
        platform = path.parent.name
        candidates = PLATFORM_READ_ORDER.get(platform, PLATFORM_READ_ORDER["fallback"])
        content_path = next((path / name for name in candidates if (path / name).is_file()), None)
        if content_path is None:
            raise FileNotFoundError(f"No readable content file found in {path}")
        content = content_path.read_text(encoding="utf-8")
        title = self._first_heading(content) or path.name
        source = self._extract_source(content)
        date = self._date_from_name(path.name)
        return InboxPost(path.name, path, platform, title, source, date, content, content_path.name)

    def _first_heading(self, content: str) -> str:
        for line in content.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return ""

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

    def _archive_post(self, post: InboxPost, topic: str) -> Path:
        topic_dir = self.paths.archive / self._archive_topic_slug(topic)
        topic_dir.mkdir(parents=True, exist_ok=True)
        dest = topic_dir / f"[{post.platform}] {post.name}"
        counter = 2
        original = dest
        while dest.exists():
            dest = Path(f"{original}-{counter}")
            counter += 1
        shutil.move(str(post.path), str(dest))
        return dest

    def _archive_topic_slug(self, topic: str) -> str:
        return normalize_slug(topic.rsplit("/", 1)[-1])

    def _legacy_path(self, path: Path) -> str:
        try:
            return path.relative_to(self.paths.root).as_posix()
        except ValueError:
            return str(path)
