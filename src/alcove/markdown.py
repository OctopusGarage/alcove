from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata

import yaml


RESERVED_FILENAMES = {"index.md", "log.md"}


@dataclass(frozen=True)
class MarkdownDoc:
    frontmatter: dict
    body: str
    path: Path | None = None


def normalize_slug(text: str, max_len: int = 80) -> str:
    value = unicodedata.normalize("NFKC", str(text or "").strip()).lower()
    chars: list[str] = []
    previous_dash = False
    for char in value:
        category = unicodedata.category(char)
        if category.startswith(("L", "N")):
            chars.append(char)
            previous_dash = False
        elif not previous_dash:
            chars.append("-")
            previous_dash = True
    slug = "".join(chars).strip("-")
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug or "item"


class MarkdownRepository:
    def read_doc(self, path: Path | str) -> MarkdownDoc:
        doc_path = Path(path)
        content = doc_path.read_text(encoding="utf-8")
        frontmatter, body = self._split_frontmatter(content)
        return MarkdownDoc(frontmatter=frontmatter, body=body, path=doc_path)

    def write_doc(self, path: Path | str, doc: MarkdownDoc) -> Path:
        doc_path = Path(path)
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        fm = yaml.safe_dump(
            doc.frontmatter,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )
        body = doc.body.rstrip() + "\n"
        doc_path.write_text(f"---\n{fm}---\n{body}", encoding="utf-8")
        return doc_path

    def list_docs(self, root: Path | str, type_filter: str | None = None) -> list[MarkdownDoc]:
        root_path = Path(root)
        docs: list[MarkdownDoc] = []
        if not root_path.exists():
            return docs
        for path in sorted(root_path.rglob("*.md"), key=lambda p: p.as_posix()):
            if path.name in RESERVED_FILENAMES:
                continue
            doc = self.read_doc(path)
            if type_filter and doc.frontmatter.get("type") != type_filter:
                continue
            docs.append(doc)
        return docs

    def unique_path(self, directory: Path | str, slug: str) -> Path:
        directory_path = Path(directory)
        candidate = directory_path / f"{normalize_slug(slug)}.md"
        if not candidate.exists() and candidate.name not in RESERVED_FILENAMES:
            return candidate
        counter = 2
        while True:
            candidate = directory_path / f"{normalize_slug(slug)}-{counter}.md"
            if not candidate.exists() and candidate.name not in RESERVED_FILENAMES:
                return candidate
            counter += 1

    def _split_frontmatter(self, content: str) -> tuple[dict, str]:
        if not content.startswith("---\n"):
            return {}, content
        parts = re.split(r"^---\s*$", content, maxsplit=2, flags=re.MULTILINE)
        if len(parts) < 3:
            return {}, content
        try:
            frontmatter = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            return {}, content
        if not isinstance(frontmatter, dict):
            return {}, content
        body = parts[2].lstrip("\n")
        return frontmatter, body
