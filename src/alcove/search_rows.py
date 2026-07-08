from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from alcove.external_index import ExternalItemReference
from alcove.markdown import MarkdownDoc
from alcove.okf import (
    frontmatter_confidence,
    frontmatter_date,
    relative_doc_path,
    require_doc_path,
    string_or_none,
    value_list,
)


class SearchRow(TypedDict):
    root: str
    type: str | None
    title: str
    domain: str | None
    topic: str | None
    platform: str | None
    date: str
    tags: list[str]
    confidence: float
    status: str
    resource: str | None
    notes: str
    path: str


class SearchRowBuilder:
    def __init__(self, knowledge_root: Path | None) -> None:
        self.knowledge_root = knowledge_root

    def knowledge_doc(self, doc: MarkdownDoc) -> SearchRow:
        frontmatter = doc.frontmatter
        path = require_doc_path(doc, "Search result document")
        return {
            "root": "knowledge",
            "type": string_or_none(frontmatter.get("type")),
            "title": string_or_none(frontmatter.get("title")) or path.stem,
            "domain": string_or_none(frontmatter.get("domain")),
            "topic": string_or_none(frontmatter.get("topic")),
            "platform": string_or_none(frontmatter.get("platform")),
            "date": frontmatter_date(frontmatter),
            "tags": value_list(frontmatter.get("tags")),
            "confidence": frontmatter_confidence(frontmatter),
            "status": string_or_none(frontmatter.get("status")) or "active",
            "resource": string_or_none(frontmatter.get("resource")),
            "notes": doc.body,
            "path": relative_doc_path(doc, self.knowledge_root),
        }

    def pin_doc(self, doc: MarkdownDoc) -> SearchRow:
        frontmatter = doc.frontmatter
        path = require_doc_path(doc, "Pin document")
        return {
            "root": "pins",
            "type": "Pin",
            "title": string_or_none(frontmatter.get("title")) or path.stem,
            "domain": None,
            "topic": None,
            "platform": None,
            "date": frontmatter_date(frontmatter),
            "tags": value_list(frontmatter.get("tags")),
            "confidence": 0.5,
            "status": string_or_none(frontmatter.get("status")) or "active",
            "resource": None,
            "notes": doc.body,
            "path": f"pins/{path.name}",
        }

    def pin_item(self, pin: Any) -> SearchRow:
        return {
            "root": "pins",
            "type": "Pin",
            "title": string_or_none(pin.title) or pin.id,
            "domain": None,
            "topic": None,
            "platform": None,
            "date": str(pin.created_at or "")[:10],
            "tags": value_list(pin.tags),
            "confidence": 0.5,
            "status": string_or_none(pin.status) or "active",
            "resource": None,
            "notes": string_or_none(pin.description) or "",
            "path": f"pins/{pin.path.name}",
        }

    def task_item(self, item_type: str, item: dict[str, Any], collection: str) -> SearchRow:
        item_id = str(item.get("id") or "")
        return {
            "root": "tasks",
            "type": item_type,
            "title": string_or_none(item.get("title")) or item_id,
            "domain": None,
            "topic": None,
            "platform": None,
            "date": frontmatter_date(item),
            "tags": value_list(item.get("tags")),
            "confidence": 0.5,
            "status": string_or_none(item.get("status")) or "active",
            "resource": None,
            "notes": string_or_none(item.get("notes")) or "",
            "path": f"tasks/tasks.json#{collection}/{item_id}",
        }

    def idea_item(self, idea: Any) -> SearchRow:
        return {
            "root": "tasks",
            "type": "Idea",
            "title": string_or_none(idea.title) or idea.id,
            "domain": None,
            "topic": None,
            "platform": None,
            "date": str(idea.created_at or "")[:10],
            "tags": value_list(idea.tags),
            "confidence": 0.5,
            "status": string_or_none(idea.status) or "active",
            "resource": None,
            "notes": string_or_none(idea.notes) or "",
            "path": f"tasks/tasks.json#ideas/{idea.id}",
        }

    def task_record(self, task: Any) -> SearchRow:
        return {
            "root": "tasks",
            "type": "Task",
            "title": string_or_none(task.title) or task.id,
            "domain": None,
            "topic": None,
            "platform": None,
            "date": str(task.created_at or "")[:10],
            "tags": value_list(task.tags),
            "confidence": 0.5,
            "status": string_or_none(task.status) or "pending",
            "resource": None,
            "notes": string_or_none(task.notes) or "",
            "path": f"tasks/tasks.json#tasks/{task.id}",
        }

    def mount_item(self, item: dict[str, Any]) -> SearchRow:
        mount_id = str(item.get("mount_id") or "")
        rel = str(item.get("relative_path") or "")
        ref = ExternalItemReference.mount(mount_id, rel)
        return {
            "root": "mounts",
            "type": "Mounted Item",
            "title": string_or_none(item.get("title")) or rel,
            "domain": None,
            "topic": None,
            "platform": None,
            "date": frontmatter_date(item),
            "tags": value_list(item.get("tags")),
            "confidence": 0.5,
            "status": string_or_none(item.get("status")) or "active",
            "resource": string_or_none(item.get("path")),
            "notes": string_or_none(item.get("text")) or "",
            "path": ref.path,
        }

    def connector_item(self, connector_id: str, item: dict[str, Any]) -> SearchRow:
        rel = str(item.get("relative_path") or "")
        ref = ExternalItemReference.connector(connector_id, rel)
        item_type = string_or_none(item.get("type")) or "Connector Item"
        return {
            "root": "connectors",
            "type": item_type,
            "title": string_or_none(item.get("title")) or rel,
            "domain": string_or_none(item.get("account")),
            "topic": string_or_none(item.get("folder_path")),
            "platform": connector_id,
            "date": frontmatter_date(item),
            "tags": value_list(item.get("tags")),
            "confidence": 0.5,
            "status": string_or_none(item.get("status")) or "active",
            "resource": string_or_none(item.get("resource")) or string_or_none(item.get("path")),
            "notes": string_or_none(item.get("text")) or "",
            "path": ref.path,
        }
