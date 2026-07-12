from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Callable

from alcove.markdown import MarkdownDoc, MarkdownRepository, normalize_slug


@dataclass(frozen=True)
class DerivedOkfDocument:
    key: str
    doc: MarkdownDoc


class DerivedOkfWriter:
    def __init__(self, repository: MarkdownRepository | None = None) -> None:
        self.repository = repository or MarkdownRepository()

    def write_doc(self, path: Path, doc: MarkdownDoc) -> Path:
        return self.repository.write_doc(path, doc)

    def write_item_docs(self, directory: Path, docs: list[DerivedOkfDocument]) -> list[Path]:
        return self.write_named_docs(directory, docs, filename_for=stable_derived_item_filename)

    def write_named_docs(
        self,
        directory: Path,
        docs: list[DerivedOkfDocument],
        *,
        filename_for: Callable[[str], str],
    ) -> list[Path]:
        directory.mkdir(parents=True, exist_ok=True)
        active_paths = set()
        written_paths = []
        for doc in docs:
            path = directory / filename_for(doc.key)
            active_paths.add(path)
            written_paths.append(self.repository.write_doc(path, doc.doc))
        for stale_path in sorted(directory.glob("*.md"), key=lambda path: path.as_posix()):
            if stale_path not in active_paths:
                stale_path.unlink()
        return written_paths


def stable_derived_item_filename(key: str) -> str:
    value = str(key or "item")
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    slug = normalize_slug(value, max_len=72)
    return f"{slug}-{digest}.md"


def stable_slug_filename(key: str) -> str:
    return f"{normalize_slug(key)}.md"
