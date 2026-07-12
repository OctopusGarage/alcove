from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class InboxPost:
    name: str
    path: Path
    platform: str
    identifier: str
    title: str
    source: str | None
    date: str | None
    content: str
    content_source: str
    capture_status: str = ""
    capture_warnings: list[str] = field(default_factory=list)
    content_files: list[dict] = field(default_factory=list)
    content_outline: list[dict] = field(default_factory=list)
    review_content: str = ""
    review_summary: str = ""
    review_outline: list[dict] = field(default_factory=list)
    review_content_truncated: bool = False
    review_content_omitted_chars: int = 0
    content_truncated: bool = False
    full_content_command: str = ""
    full_content_hint: str = ""


@dataclass(frozen=True)
class InboxNoteRequest:
    name: str
    topic: str
    summary: str
    tags: list[str] = field(default_factory=list)
    selected_takeaways: list[str] = field(default_factory=list)
    why: str = ""
    connection: str = ""
    action: str = ""
    personal_note: str = ""
    no_auto_tags: bool = False
    supersede_similar: bool = False


@dataclass(frozen=True)
class InboxProcessResult:
    archive_path: Path
    source_path: Path
    concept_path: Path | None
    tags: list[str] = field(default_factory=list)
    confidence: dict | None = None
    superseded: list[str] = field(default_factory=list)
