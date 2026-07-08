from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


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
