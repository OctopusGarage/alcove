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
    "image-ocr": ("summary.md", "ocr.md", "ocr.txt", "post.md"),
    "manual": ("note.md", "post.md", "summary.md"),
    "fallback": ("post.md", "summary.md", "article.md", "ocr.md", "ocr.txt", "ocr-merge.txt"),
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
        identifier = f"{platform}/{path.name}"
        metadata = self._capture_metadata(path)
        content_paths = self._content_paths(path, platform, metadata)
        if not content_paths:
            raise FileNotFoundError(f"No readable content file found in {path}")
        content, content_paths, content_file_rows = self._read_content_files(
            path,
            content_paths,
            metadata,
        )
        title = self._title_from_content_or_metadata(content, metadata, path.name)
        source = self._extract_source(content) or self._metadata_string(
            metadata, "source_url", "canonical_url"
        )
        date = self._date_from_name(path.name) or self._metadata_date(metadata)
        content_source = ", ".join(
            content_path.relative_to(path).as_posix() for content_path in content_paths
        )
        review_content, review_content_truncated, review_content_omitted_chars = (
            self._review_content(content_file_rows)
        )
        return InboxPost(
            path.name,
            path,
            platform,
            identifier,
            title,
            source,
            date,
            content,
            content_source,
            self._metadata_string(metadata, "status") or "ready",
            self._metadata_warnings(metadata),
            self._content_file_rows_with_read_hints(content_file_rows, identifier),
            self._content_outline(content_file_rows),
            review_content,
            self._review_summary(content_file_rows, self._metadata_warnings(metadata)),
            self._review_outline(content_file_rows),
            review_content_truncated,
            review_content_omitted_chars,
            self._content_has_truncation_marker(content),
            f"alcove inbox read {identifier} --full --json",
            "Run full_content_command from the managed KB root, or add --kb <name> from elsewhere. The --full flag requests an unabridged read payload.",
        )

    def _content_paths(self, path: Path, platform: str, metadata: dict) -> list[Path]:
        metadata_paths = self._existing_unique_content_paths(
            self._metadata_content_paths(path, platform, metadata),
            path,
        )
        if metadata_paths:
            return metadata_paths
        return self._existing_unique_content_paths(
            self._fallback_content_paths(path, platform), path
        )[:1]

    def _existing_unique_content_paths(self, candidates: list[Path], root: Path) -> list[Path]:
        paths: list[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            try:
                relative = candidate.relative_to(root).as_posix()
            except ValueError:
                continue
            if relative in seen:
                continue
            seen.add(relative)
            if candidate.is_file():
                paths.append(candidate)
        return paths

    def _read_content_files(
        self,
        root: Path,
        content_paths: list[Path],
        metadata: dict,
    ) -> tuple[str, list[Path], list[dict]]:
        block_entries: list[tuple[str, Path, str]] = []
        used_paths: list[Path] = []
        rows: list[dict] = []
        seen: dict[str, str] = {}
        declared = self._declared_content_files(metadata)
        for path in content_paths:
            raw = path.read_text(encoding="utf-8")
            block = raw.strip()
            relative = path.relative_to(root).as_posix()
            omitted_chars = self._omitted_chars(block)
            review_excerpt, review_excerpt_truncated, review_excerpt_omitted_chars = (
                self._review_excerpt_with_metadata(block)
            )
            row = {
                "path": relative,
                "kind": self._content_kind(relative, declared),
                "byte_count": len(raw.encode("utf-8")),
                "char_count": len(raw),
                "included": False,
                "duplicate_of": "",
                "merged_into": "",
                "truncated": omitted_chars > 0,
                "omitted_chars": omitted_chars,
                "review_excerpt": review_excerpt,
                "review_excerpt_truncated": review_excerpt_truncated,
                "review_excerpt_omitted_chars": review_excerpt_omitted_chars,
                "tail_excerpt": self._tail_excerpt(block),
            }
            if not block:
                rows.append(row)
                continue
            normalized = self._normalize_content_block(block)
            if normalized in seen:
                row["duplicate_of"] = seen[normalized]
                rows.append(row)
                continue
            lead_duplicate = self._same_review_lead_row(row, rows)
            if lead_duplicate is not None:
                existing_index, existing_row = lead_duplicate
                existing_excerpt = str(existing_row.get("review_excerpt") or "")
                current_excerpt = str(row.get("review_excerpt") or "")
                if len(current_excerpt) <= len(existing_excerpt):
                    row["merged_into"] = str(existing_row.get("path") or "")
                    rows.append(row)
                    continue
                rows[existing_index] = {
                    **existing_row,
                    "included": False,
                    "merged_into": relative,
                }
                used_paths = [
                    used_path
                    for used_path in used_paths
                    if used_path != root / str(existing_row.get("path") or "")
                ]
                block_entries = [
                    entry for entry in block_entries if entry[0] != existing_row.get("path")
                ]
            seen[normalized] = relative
            used_paths.append(path)
            row["included"] = True
            rows.append(row)
            if block_entries:
                block = f"## Content from {relative}\n\n{block}"
            block_entries.append((relative, path, block))
        blocks = [block for _, _, block in block_entries]
        return "\n\n---\n\n".join(blocks), used_paths, rows

    def _content_file_rows_with_read_hints(
        self,
        rows: list[dict],
        identifier: str,
    ) -> list[dict]:
        return [
            {
                **row,
                "read_command": f"alcove inbox read {identifier} --full --json",
                "read_hint": (
                    "Use read_command for the full merged payload; use path to locate this "
                    "source file inside the inbox item when exact file provenance is needed."
                ),
            }
            for row in rows
        ]

    def _content_outline(self, rows: list[dict]) -> list[dict]:
        return [
            {
                "path": str(row.get("path") or ""),
                "kind": str(row.get("kind") or ""),
                "truncated": bool(row.get("truncated")),
                "omitted_chars": int(row.get("omitted_chars") or 0),
                "excerpt": str(row.get("review_excerpt") or ""),
                "tail_excerpt": str(row.get("tail_excerpt") or ""),
            }
            for row in rows
            if row.get("included")
        ]

    def _review_outline(self, rows: list[dict]) -> list[dict]:
        outline: list[dict] = []
        for row in rows:
            if not row.get("included"):
                continue
            path = str(row.get("path") or "")
            text = str(row.get("review_excerpt") or "")
            sections = self._review_sections(text)
            if not sections:
                sections = self._long_review_sections(row)
            if sections:
                outline.append({"path": path, "sections": sections})
        return outline

    def _long_review_sections(self, row: dict) -> list[dict]:
        if not row.get("review_excerpt_truncated") and not row.get("review_excerpt_omitted_chars"):
            return []
        excerpt = str(row.get("review_excerpt") or "")
        if not excerpt:
            return []
        lead_text, _, later_text = excerpt.partition("...[omitted ")
        later_text = later_text.partition("chars in review excerpt]...")[2] if later_text else ""
        sections: list[dict] = []
        lead = self._first_complete_summary_sentence(lead_text, max_chars=180)
        if lead:
            sections.append({"title": "Lead", "excerpt": lead})
        later_source = str(row.get("tail_excerpt") or later_text or "")
        later = self._first_complete_summary_sentence(later_source, max_chars=180)
        if later and later != lead:
            sections.append({"title": "Later context", "excerpt": later})
        omitted = int(row.get("review_excerpt_omitted_chars") or 0)
        if omitted:
            sections.append(
                {
                    "title": "Full content",
                    "excerpt": f"{omitted} chars omitted from review excerpt; use read_command for the full source.",
                }
            )
        return sections

    def _review_summary(self, rows: list[dict], warnings: list[str] | None = None) -> str:
        warning_prefix = self._warning_summary_prefix(warnings or [])
        summary = ""
        for row in rows:
            if str(row.get("kind") or "") != "summary":
                continue
            summary = str(row.get("review_excerpt") or "").strip()
            if (
                row.get("included")
                and not row.get("duplicate_of")
                and self._looks_complete_summary(summary)
            ):
                return self._with_warning_prefix(
                    self._summary_with_ocr_excerpt(summary, rows),
                    warning_prefix,
                )
            break
        for row in rows:
            if not row.get("included") or str(row.get("kind") or "") == "summary":
                continue
            outline_summary = self._summary_from_sections(
                self._review_sections(str(row.get("review_excerpt") or ""))
            )
            if outline_summary:
                return self._with_warning_prefix(outline_summary, warning_prefix)
            candidate = self._first_complete_summary_sentence(str(row.get("review_excerpt") or ""))
            if candidate:
                return self._with_warning_prefix(candidate, warning_prefix)
        return self._with_warning_prefix(summary, warning_prefix)

    def _warning_summary_prefix(self, warnings: list[str]) -> str:
        clean = [warning.strip() for warning in warnings if warning.strip()]
        if not clean:
            return ""
        return f"Warnings: {'; '.join(clean[:2])}. "

    def _with_warning_prefix(self, summary: str, prefix: str) -> str:
        if not prefix:
            return summary
        return self._compact_excerpt(f"{prefix}{summary}", max_chars=520)

    def _summary_with_ocr_excerpt(self, summary: str, rows: list[dict]) -> str:
        ocr = self._first_ocr_summary_sentence(rows)
        if not ocr or ocr.casefold() in summary.casefold():
            return summary
        return self._compact_excerpt(f"{summary} OCR: {ocr}", max_chars=480)

    def _first_ocr_summary_sentence(self, rows: list[dict]) -> str:
        for row in rows:
            if not row.get("included"):
                continue
            kind = str(row.get("kind") or "").casefold()
            path = str(row.get("path") or "").casefold()
            if "ocr" not in kind and "ocr" not in path:
                continue
            candidate = self._first_complete_summary_sentence(str(row.get("review_excerpt") or ""))
            if candidate:
                return candidate
        return ""

    def _summary_from_sections(self, sections: list[dict], max_chars: int = 480) -> str:
        if len(sections) < 2:
            return ""
        selected: list[str] = []
        for section in self._summary_sections(sections):
            excerpt = self._strip_leading_section_title(str(section.get("excerpt") or ""))
            sentence = self._substantive_summary_sentence(excerpt, max_chars=220)
            if not sentence:
                continue
            if sentence not in selected:
                selected.append(sentence)
            if len(selected) >= 3:
                break
        return self._compact_excerpt(
            self._clean_summary_join(" ".join(selected)), max_chars=max_chars
        )

    def _clean_summary_join(self, value: str) -> str:
        text = re.sub(r"\s+", " ", value).strip()
        text = re.sub(r"(?<=[.!?。！？])\s+[.!?。！？](?=\s|$)", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _substantive_summary_sentence(self, text: str, max_chars: int = 220) -> str:
        normalized = re.sub(r"\s+", " ", text).strip()
        if not normalized:
            return ""
        sentences = [
            sentence.strip() for sentence in re.findall(r".*?[.!?。！？](?=\s|$)", normalized)
        ]
        if not sentences:
            return self._compact_excerpt(normalized, max_chars=max_chars)
        selected = sentences[:2] if len(sentences) > 1 and len(sentences[0]) < 80 else sentences[:1]
        return self._compact_excerpt(" ".join(selected), max_chars=max_chars)

    def _summary_sections(self, sections: list[dict]) -> list[dict]:
        priority = ["Why it exists", "Overview", "Workflow", "Commands", "Bundle", "Install"]
        selected: list[dict] = []
        used: set[int] = set()
        for wanted in priority:
            for index, section in enumerate(sections):
                if index in used:
                    continue
                title = str(section.get("title") or "")
                if title.casefold() == wanted.casefold():
                    selected.append(section)
                    used.add(index)
                    break
        for index, section in enumerate(sections):
            if index not in used:
                selected.append(section)
        return selected

    def _looks_complete_summary(self, summary: str) -> bool:
        text = summary.strip()
        return len(text) >= 20 and text.endswith((".", "!", "?", "。", "！", "？"))

    def _first_complete_summary_sentence(self, text: str, max_chars: int = 280) -> str:
        normalized = re.sub(r"\s+", " ", text).strip()
        if not normalized:
            return ""
        normalized = self._strip_leading_section_title(normalized)
        sentences = re.findall(r".*?[.!?。！？](?=\s|$)", normalized)
        if sentences:
            return self._compact_excerpt(sentences[0].strip(), max_chars=max_chars)
        return self._compact_excerpt(normalized, max_chars=max_chars)

    def _strip_leading_section_title(self, text: str) -> str:
        for marker in [
            "Why it exists",
            "What it does",
            "How it works",
            "Overview",
            "Workflow",
            "Commands",
            "Bundle",
            "Install",
            "01 Start",
            "02 Capture",
            "03 Validate",
            "04 Sink",
            "摘要",
        ]:
            if text.casefold().startswith(marker.casefold()):
                return text[len(marker) :].strip(" :-")
        return text

    def _review_sections(self, text: str) -> list[dict]:
        markers = self._review_section_markers(text)
        if not markers:
            return []
        sections: list[dict] = []
        for index, (start, title) in enumerate(markers):
            end = markers[index + 1][0] if index + 1 < len(markers) else len(text)
            body_start = start + len(title)
            excerpt = self._compact_excerpt(text[body_start:end].strip(" :-\n"), max_chars=220)
            if excerpt:
                sections.append({"title": title, "excerpt": excerpt})
        return sections[:12]

    def _review_section_markers(self, text: str) -> list[tuple[int, str]]:
        marker_pattern = re.compile(
            r"(?<!\w)("
            r"(?i:Why it exists|What it does|How it works|Overview|Workflow|Commands|"
            r"Bundle|Install|Safety|Limits|Examples)|"
            r"\d{2}\s+[A-Z][A-Za-z0-9-]{2,24}"
            r")\b"
        )
        markers: list[tuple[int, str]] = []
        seen_titles: set[str] = set()
        for match in marker_pattern.finditer(text):
            title = re.sub(r"\s+", " ", match.group(1)).strip()
            if title[:1].islower():
                continue
            if title.casefold() in seen_titles:
                continue
            seen_titles.add(title.casefold())
            markers.append((match.start(1), title))
        if len(markers) >= 2:
            return markers
        line_markers = [
            (match.start(1), match.group(1).strip())
            for match in re.finditer(r"(?m)^(#{1,3}\s+.+|[-*]\s+.+|`[^`]+`)$", text)
        ]
        return line_markers if len(line_markers) >= 2 else []

    def _review_content(self, rows: list[dict], max_chars: int = 5000) -> tuple[str, bool, int]:
        parts = self._dedupe_review_parts(
            [
                str(row.get("review_excerpt") or "").strip()
                for row in rows
                if row.get("included") and row.get("review_excerpt")
            ]
        )
        joined_parts = "\n\n".join(parts)
        text, truncated, omitted_chars = self._compact_excerpt_with_metadata(
            joined_parts,
            max_chars=max_chars,
            preserve_blocks=len(parts) == 1 and "\n" in joined_parts,
        )
        excerpt_omitted_chars = sum(
            int(row.get("review_excerpt_omitted_chars") or 0) for row in rows if row.get("included")
        )
        return (
            text,
            truncated
            or any(row.get("review_excerpt_truncated") for row in rows if row.get("included")),
            omitted_chars + excerpt_omitted_chars,
        )

    def _dedupe_review_parts(self, parts: list[str]) -> list[str]:
        selected: list[str] = []
        for part in parts:
            normalized = self._normalize_content_block(part)
            if not normalized:
                continue
            replaced = False
            for index, existing in enumerate(selected):
                existing_normalized = self._normalize_content_block(existing)
                if normalized in existing_normalized:
                    replaced = True
                    break
                if existing_normalized in normalized:
                    selected[index] = part
                    replaced = True
                    break
                if self._same_review_lead(existing_normalized, normalized):
                    if len(part) > len(existing):
                        selected[index] = part
                    replaced = True
                    break
            if not replaced:
                selected.append(part)
        return selected

    def _same_review_lead(self, left: str, right: str, words: int = 8) -> bool:
        left_words = left.split()[:words]
        right_words = right.split()[:words]
        return len(left_words) == words and left_words == right_words

    def _same_review_lead_row(
        self,
        row: dict,
        rows: list[dict],
    ) -> tuple[int, dict] | None:
        current = self._normalize_content_block(str(row.get("review_excerpt") or ""))
        if not current:
            return None
        for index, existing in enumerate(rows):
            if not existing.get("included"):
                continue
            existing_excerpt = self._normalize_content_block(
                str(existing.get("review_excerpt") or "")
            )
            if self._same_review_lead(existing_excerpt, current):
                return index, existing
        return None

    def _content_has_truncation_marker(self, content: str) -> bool:
        return bool(re.search(r"\[truncated \d+ chars\]", content))

    def _omitted_chars(self, content: str) -> int:
        match = re.search(r"\[truncated (\d+) chars\]", content)
        return int(match.group(1)) if match else 0

    def _review_excerpt(self, content: str, max_chars: int = 5000) -> str:
        return self._review_excerpt_with_metadata(content, max_chars=max_chars)[0]

    def _review_excerpt_with_metadata(
        self, content: str, max_chars: int = 5000
    ) -> tuple[str, bool, int]:
        if not content.strip():
            return "", False, 0
        if self._content_has_truncation_marker(content):
            text, truncated, omitted_chars = self._head_tail_excerpt_with_metadata(
                content,
                max_chars=max_chars,
            )
            return text, truncated, omitted_chars + self._omitted_chars(content)
        preferred = self._prefer_main_content(content)
        lines = self._meaningful_lines(
            preferred,
            max_lines=None if len(preferred) <= max_chars else 8,
        )
        return self._compact_excerpt_with_metadata(
            "\n".join(lines),
            max_chars=max_chars,
            preserve_blocks=True,
        )

    def _tail_excerpt(self, content: str, max_chars: int = 500) -> str:
        return self._tail_excerpt_with_metadata(content, max_chars=max_chars)[0]

    def _tail_excerpt_with_metadata(
        self,
        content: str,
        max_chars: int = 500,
    ) -> tuple[str, bool, int]:
        match = re.search(r"\[truncated \d+ chars\]", content)
        if not match:
            return "", False, 0
        before_marker = content[: match.start()]
        return self._compact_excerpt_with_metadata(before_marker[-max_chars:], max_chars=max_chars)

    def _head_tail_excerpt_with_metadata(
        self,
        content: str,
        max_chars: int = 500,
    ) -> tuple[str, bool, int]:
        match = re.search(r"\[truncated \d+ chars\]", content)
        if not match:
            return self._compact_excerpt_with_metadata(content, max_chars=max_chars)
        before_marker = re.sub(r"\s+", " ", content[: match.start()]).strip()
        if len(before_marker) <= max_chars:
            return before_marker, False, 0
        marker_budget = 42
        head_chars = max((max_chars - marker_budget) // 2, 80)
        tail_chars = max(max_chars - marker_budget - head_chars, 80)
        head = self._clean_right_boundary(before_marker[:head_chars])
        tail = self._clean_left_boundary(before_marker[-tail_chars:])
        omitted = max(len(before_marker) - len(head) - len(tail), 0)
        marker_text = f"...[omitted {omitted} chars in review excerpt]..."
        return f"{head}\n\n{marker_text}\n\n{tail}", True, omitted

    def _clean_left_boundary(self, text: str) -> str:
        stripped = text.lstrip()
        match = re.search(r"[\s。！？.!?]", stripped)
        if match is None or match.end() >= len(stripped):
            return stripped
        return stripped[match.end() :].lstrip()

    def _clean_right_boundary(self, text: str) -> str:
        stripped = text.rstrip()
        index = max(
            stripped.rfind(separator) for separator in (" ", "。", "！", "？", ".", "!", "?")
        )
        if index <= 0:
            return stripped
        return stripped[: index + 1].rstrip()

    def _meaningful_lines(self, content: str, max_lines: int | None = 8) -> list[str]:
        lines: list[str] = []
        heading = self._first_heading(content)
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped == "---":
                continue
            if stripped.lower().startswith(("source:", "source url:")):
                continue
            if heading and stripped.lstrip("# ").startswith(heading):
                stripped = stripped.lstrip("# ").removeprefix(heading).strip()
                if not stripped:
                    continue
            lines.append(stripped)
            if max_lines is not None and len(lines) >= max_lines:
                break
        return lines

    def _prefer_main_content(self, content: str) -> str:
        text = content.strip()
        for marker in [
            "Why it exists",
            "What it does",
            "How it works",
            "Overview",
            "核心",
            "摘要",
        ]:
            index = text.casefold().find(marker.casefold())
            if 0 <= index <= 1200:
                return text[index:]
        return text

    def _first_heading(self, content: str) -> str:
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("# ").strip()
        return ""

    def _compact_excerpt(self, content: str, max_chars: int = 500) -> str:
        return self._compact_excerpt_with_metadata(content, max_chars=max_chars)[0]

    def _compact_excerpt_with_metadata(
        self,
        content: str,
        max_chars: int = 500,
        preserve_blocks: bool = False,
    ) -> tuple[str, bool, int]:
        text = re.sub(r"\[truncated \d+ chars\]", "", content)
        if preserve_blocks:
            text = self._compact_blocks(text)
        else:
            text = re.sub(r"\s+", " ", text).strip()
        if len(text) <= max_chars:
            return text, False, 0
        selected = text[: max_chars - 1].rstrip()
        return selected + "…", True, max(len(text) - len(selected), 0)

    def _compact_blocks(self, content: str) -> str:
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in content.splitlines()]
        blocks: list[str] = []
        blank = False
        for line in lines:
            if not line:
                blank = bool(blocks)
                continue
            if blank:
                blocks.append("")
            blocks.append(line)
            blank = False
        return "\n".join(blocks).strip()

    def _declared_content_files(self, metadata: dict) -> dict[str, dict]:
        content_files = metadata.get("content_files")
        if not isinstance(content_files, list):
            return {}
        return {
            str(entry["path"]): entry
            for entry in content_files
            if isinstance(entry, dict) and isinstance(entry.get("path"), str)
        }

    def _content_kind(self, relative: str, declared: dict[str, dict]) -> str:
        declared_kind = declared.get(relative, {}).get("kind")
        if isinstance(declared_kind, str) and declared_kind.strip():
            return declared_kind.strip()
        stem = Path(relative).stem.lower()
        if stem in {"summary", "article", "post", "ocr"}:
            return stem
        return "content"

    def _normalize_content_block(self, value: str) -> str:
        return " ".join(value.split()).strip().lower()

    def _content_path(self, path: Path, platform: str, metadata: dict) -> Path | None:
        candidates = [
            *self._metadata_content_paths(path, platform, metadata),
            *self._fallback_content_paths(path, platform),
        ]
        seen: set[str] = set()
        for candidate in candidates:
            try:
                relative = candidate.relative_to(path).as_posix()
            except ValueError:
                continue
            if relative in seen:
                continue
            seen.add(relative)
            if candidate.is_file():
                return candidate
        return None

    def _metadata_content_paths(self, path: Path, platform: str, metadata: dict) -> list[Path]:
        content_files = metadata.get("content_files")
        if not isinstance(content_files, list):
            return []
        entries = [entry for entry in content_files if isinstance(entry, dict)]
        order = PLATFORM_READ_ORDER.get(platform, PLATFORM_READ_ORDER["fallback"])
        return [
            path / entry["path"]
            for entry in sorted(entries, key=lambda entry: self._content_file_rank(entry, order))
            if isinstance(entry.get("path"), str)
            and self._safe_relative_content_path(path, entry["path"])
        ]

    def _content_file_rank(self, entry: dict, order: tuple[str, ...]) -> tuple[int, int]:
        value = str(entry.get("kind") or entry.get("role") or entry.get("path") or "")
        path = str(entry.get("path") or "")
        text = f"{value} {path}".lower()
        for index, preferred in enumerate(order):
            stem = Path(preferred).stem.lower()
            if preferred.lower() == path.lower() or stem in text:
                return (index, 0)
        if bool(entry.get("required_for_review")):
            return (len(order), 0)
        return (len(order), 1)

    def _fallback_content_paths(self, path: Path, platform: str) -> list[Path]:
        order = PLATFORM_READ_ORDER.get(platform, PLATFORM_READ_ORDER["fallback"])
        return [path / name for name in order]

    def _safe_relative_content_path(self, root: Path, value: str) -> bool:
        candidate = Path(value)
        if candidate.is_absolute():
            return False
        try:
            root_resolved = root.resolve(strict=False)
            (root / candidate).resolve(strict=False).relative_to(root_resolved)
        except (OSError, ValueError):
            return False
        return True

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

    def _metadata_warnings(self, metadata: dict) -> list[str]:
        warnings = metadata.get("warnings")
        if not isinstance(warnings, list):
            return []
        return [str(warning).strip() for warning in warnings if str(warning).strip()]

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
