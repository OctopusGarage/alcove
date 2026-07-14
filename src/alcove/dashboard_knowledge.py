from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alcove.home import AlcoveHome
from alcove.markdown import MarkdownRepository

CAPTURE_ENTRY_MARKERS = frozenset(
    {
        "capture.json",
        "post.md",
        "summary.md",
        "article.md",
    }
)


class DashboardKnowledgeRows:
    """Managed knowledge-base rows for dashboard snapshots."""

    def __init__(self, home: AlcoveHome) -> None:
        self.home = home

    def rows(self, kb_rows: list[Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for kb in kb_rows:
            all_knowledge_files = self.files_under(kb.path / "knowledge", "*.md")
            candidate_files = [
                path
                for path in all_knowledge_files
                if not self.is_structural_knowledge_path(path, kb.path)
            ]
            knowledge_files = [
                path for path in candidate_files if self.knowledge_file_status(path) != "deleted"
            ]
            deleted_item_count = len(candidate_files) - len(knowledge_files)
            inbox_files = self.files_under(kb.path / "inbox")
            archive_files = self.files_under(kb.path / "archive")
            inbox_entries = self.content_entry_dirs(kb.path / "inbox")
            archive_entries = self.content_entry_dirs(kb.path / "archive")
            omitted_items = [
                self.omitted_knowledge_item(path, kb.path) for path in knowledge_files[5:8]
            ]
            rows.append(
                {
                    "name": kb.name,
                    "item_count": len(knowledge_files),
                    "deleted_item_count": deleted_item_count,
                    "display_limit": 5,
                    "omitted_item_count": max(len(knowledge_files) - 5, 0),
                    "omitted_items": omitted_items,
                    "inbox_count": len(inbox_entries),
                    "archive_count": len(archive_entries),
                    "updated_at": self.latest_mtime(
                        [*all_knowledge_files, *inbox_files, *archive_files]
                    ),
                    "items": [
                        self.knowledge_item(file_path, kb.path) for file_path in knowledge_files[:5]
                    ],
                    "search_items": [
                        self.knowledge_search_item(file_path, kb.path)
                        for file_path in knowledge_files
                    ],
                }
            )
        return rows

    def knowledge_file_status(self, path: Path) -> str:
        try:
            doc = MarkdownRepository().read_doc(path)
        except OSError:
            return ""
        return str(doc.frontmatter.get("status") or "").casefold()

    def files_under(self, root: Path, pattern: str = "*") -> list[Path]:
        if not root.is_dir():
            return []
        return [
            path
            for path in sorted(root.rglob(pattern), key=lambda item: item.as_posix())
            if path.is_file()
        ]

    def content_entry_dirs(self, root: Path) -> list[Path]:
        if not root.is_dir():
            return []
        return [
            path
            for path in sorted(root.rglob("*"), key=lambda item: item.as_posix())
            if path.is_dir() and self.is_content_entry_dir(path)
        ]

    def is_content_entry_dir(self, path: Path) -> bool:
        return any((path / marker).is_file() for marker in CAPTURE_ENTRY_MARKERS)

    def latest_mtime(self, paths: list[Path]) -> str:
        if not paths:
            return ""
        return datetime.fromtimestamp(max(path.stat().st_mtime for path in paths), UTC).isoformat(
            timespec="seconds"
        )

    def omitted_knowledge_item(self, path: Path, kb_root: Path) -> dict[str, str]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        doc = MarkdownRepository().read_doc(path)
        title = str(doc.frontmatter.get("title") or self.title_from_markdown(text) or path.stem)
        return {
            "title": title,
            "type": str(doc.frontmatter.get("type") or "Managed KB Item"),
            "relative_path": path.relative_to(kb_root).as_posix(),
            "search_hint": f'alcove search "{title}" --json',
        }

    def knowledge_item(self, path: Path, kb_root: Path) -> dict[str, Any]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        doc = MarkdownRepository().read_doc(path)
        title = str(doc.frontmatter.get("title") or self.title_from_markdown(text) or path.stem)
        okf_type = str(doc.frontmatter.get("type") or "Managed KB Item")
        excerpt, truncated = self.clean_markdown_excerpt(text)
        return {
            "title": title,
            "type": okf_type,
            "okf_type": okf_type,
            "domain": str(doc.frontmatter.get("domain") or ""),
            "topic": str(doc.frontmatter.get("topic") or ""),
            "status": str(doc.frontmatter.get("status") or ""),
            "confidence": self.frontmatter_confidence(doc.frontmatter),
            "relative_path": path.relative_to(kb_root).as_posix(),
            "notes": excerpt,
            "truncated": truncated,
            "updated_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(
                timespec="seconds"
            ),
        }

    def knowledge_search_item(self, path: Path, kb_root: Path) -> dict[str, str]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        doc = MarkdownRepository().read_doc(path)
        title = str(doc.frontmatter.get("title") or self.title_from_markdown(text) or path.stem)
        notes, _ = self.clean_markdown_excerpt(text, max_chars=320)
        return {
            "title": title,
            "type": str(doc.frontmatter.get("type") or "Managed KB Item"),
            "relative_path": path.relative_to(kb_root).as_posix(),
            "notes": notes,
        }

    def frontmatter_confidence(self, frontmatter: dict[str, Any]) -> float:
        try:
            return round(float(frontmatter.get("confidence", 0.5) or 0.5), 2)
        except (TypeError, ValueError):
            return 0.5

    def clean_markdown_excerpt(self, text: str, max_chars: int = 800) -> tuple[str, bool]:
        body = text
        if body.startswith("---\n"):
            _, separator, rest = body.partition("\n---\n")
            if separator:
                body = rest
        lines: list[str] = []
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped:
                if lines and lines[-1] != "":
                    lines.append("")
                continue
            if stripped.startswith(("[", "type:", "domain:", "topic:", "status:")):
                continue
            lines.append(line)
        excerpt = "\n".join(lines).strip()
        if len(excerpt) <= max_chars:
            return excerpt, False

        selected: list[str] = []
        current_len = 0
        for line in excerpt.splitlines():
            addition = len(line) + (1 if selected else 0)
            if selected and current_len + addition > max_chars:
                break
            if not selected and len(line) > max_chars:
                return self.truncate_line(line, max_chars), True
            selected.append(line)
            current_len += addition

        while selected and not selected[-1].strip():
            selected.pop()
        while selected and selected[-1].strip().startswith("#"):
            selected.pop()
            while selected and not selected[-1].strip():
                selected.pop()

        if not selected:
            return self.truncate_line(excerpt, max_chars), True
        return "\n".join(selected).strip(), True

    def truncate_line(self, text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        cutoff = text.rfind(" ", 0, max_chars)
        if cutoff < max_chars // 2:
            cutoff = max_chars
        return text[:cutoff].rstrip()

    def title_from_markdown(self, text: str) -> str:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped.removeprefix("# ").strip()
            if stripped.startswith("title:"):
                return stripped.partition(":")[2].strip().strip("'\"")
        return ""

    def is_structural_knowledge_path(self, path: Path, kb_root: Path) -> bool:
        try:
            relative_path = path.relative_to(kb_root).as_posix()
        except ValueError:
            return False
        return self.is_structural_knowledge_relative_path(relative_path)

    def is_structural_knowledge_relative_path(self, relative_path: str) -> bool:
        return relative_path == "knowledge/index.md" or relative_path.startswith(
            (
                "knowledge/domains/",
                "knowledge/tags/",
                "knowledge/topics/",
            )
        )
