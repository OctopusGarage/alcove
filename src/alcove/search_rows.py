from __future__ import annotations

from pathlib import Path
from typing import Any, NotRequired, TypedDict, cast

from alcove.external_index import ExternalItemReference
from alcove.external_presentation import ExternalIndexedItemPresenter
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
    published_at: str
    collected_at: str
    updated_at: str
    deleted_at: str
    tags: list[str]
    confidence: float
    status: str
    resource: str | None
    notes: str
    path: str
    redacted: NotRequired[bool]
    display_id: NotRequired[str]
    display_label: NotRequired[str]
    fetch_ref: NotRequired[str]
    fetch_command: NotRequired[str]
    read_ref: NotRequired[str]
    read_command: NotRequired[str]
    read_hint: NotRequired[str]
    source_ref: NotRequired[str]
    information_quality: NotRequired[dict[str, Any]]
    kb: NotRequired[str]
    source_id: NotRequired[str]
    source_label: NotRequired[str]
    origin_label: NotRequired[str]


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
            "published_at": _first_date(
                frontmatter,
                "published_at",
                "published_date",
                "date",
            ),
            "collected_at": _first_date(
                frontmatter,
                "collected_at",
                "captured_at",
                "created_at",
                "download_date",
                "exported_at",
                "imported_at",
                "indexed_at",
                "timestamp",
            ),
            "updated_at": _first_date(frontmatter, "updated_at", "last_verified"),
            "deleted_at": _first_date(frontmatter, "deleted_at"),
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
            "published_at": "",
            "collected_at": _first_date(frontmatter, "created_at", "timestamp"),
            "updated_at": _first_date(frontmatter, "updated_at"),
            "deleted_at": _first_date(frontmatter, "deleted_at"),
            "tags": value_list(frontmatter.get("tags")),
            "confidence": 0.5,
            "status": string_or_none(frontmatter.get("status")) or "active",
            "resource": None,
            "notes": doc.body,
            "path": f"pins/{path.name}",
        }

    def pin_item(self, pin: Any) -> SearchRow:
        created_at = str(pin.created_at or "")
        updated_at = str(getattr(pin, "updated_at", "") or "")
        notes = _deduplicated_search_text(
            [
                string_or_none(pin.description) or "",
                string_or_none(getattr(pin, "summary", "")) or "",
                string_or_none(getattr(pin, "content", "")) or "",
                string_or_none(getattr(pin, "kind", "")) or "",
            ]
        )
        return {
            "root": "pins",
            "type": "Pin",
            "title": string_or_none(pin.title) or pin.id,
            "domain": None,
            "topic": None,
            "platform": None,
            "date": created_at[:10],
            "published_at": "",
            "collected_at": created_at,
            "updated_at": updated_at,
            "deleted_at": "",
            "tags": value_list(pin.tags),
            "confidence": 0.5,
            "status": string_or_none(pin.status) or "active",
            "resource": None,
            "notes": notes,
            "path": f"pins/{pin.path.name}",
        }

    def project_item(self, project: Any) -> SearchRow:
        created_at = str(project.created_at or "")
        updated_at = str(project.updated_at or "")
        return {
            "root": "projects",
            "type": "Project",
            "title": string_or_none(project.alias) or "",
            "domain": None,
            "topic": None,
            "platform": None,
            "date": str(updated_at or created_at)[:10],
            "published_at": "",
            "collected_at": created_at,
            "updated_at": updated_at,
            "deleted_at": "",
            "tags": [],
            "confidence": 0.5,
            "status": "active" if project.exists else "missing",
            "resource": str(project.path),
            "notes": string_or_none(project.note) or "",
            "path": f"projects/projects.json#{project.alias}",
        }

    def prompt_item(self, prompt: Any) -> SearchRow:
        created_at = str(prompt.created_at or "")
        updated_at = str(prompt.updated_at or "")
        return {
            "root": "prompts",
            "type": "Prompt",
            "title": string_or_none(prompt.title) or prompt.id,
            "domain": string_or_none(getattr(prompt, "domain", "")),
            "topic": string_or_none(getattr(prompt, "intent", "")),
            "platform": ", ".join(value_list(getattr(prompt, "surfaces", []))) or None,
            "date": str(updated_at or created_at)[:10],
            "published_at": "",
            "collected_at": created_at,
            "updated_at": updated_at,
            "deleted_at": "",
            "tags": value_list(prompt.tags),
            "confidence": 0.5,
            "status": string_or_none(prompt.status) or "active",
            "resource": None,
            "notes": "\n".join(
                part
                for part in (
                    prompt.description,
                    string_or_none(getattr(prompt, "kind", "")) or "",
                    " ".join(value_list(getattr(prompt, "triggers", []))),
                    " ".join(prompt.use_cases),
                    prompt.content,
                )
                if part
            ),
            "path": f"prompts/{prompt.path.name}",
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
            "published_at": "",
            "collected_at": _first_date(item, "created_at", "imported_at"),
            "updated_at": _first_date(item, "updated_at", "completed_at", "archived_at"),
            "deleted_at": "",
            "tags": value_list(item.get("tags")),
            "confidence": 0.5,
            "status": string_or_none(item.get("status")) or "active",
            "resource": None,
            "notes": string_or_none(item.get("notes")) or "",
            "path": f"tasks/tasks.json#{collection}/{item_id}",
        }

    def idea_item(self, idea: Any) -> SearchRow:
        created_at = str(idea.created_at or "")
        updated_at = str(getattr(idea, "updated_at", "") or "")
        return {
            "root": "tasks",
            "type": "Idea",
            "title": string_or_none(idea.title) or idea.id,
            "domain": None,
            "topic": None,
            "platform": None,
            "date": created_at[:10],
            "published_at": "",
            "collected_at": created_at,
            "updated_at": updated_at,
            "deleted_at": "",
            "tags": value_list(idea.tags),
            "confidence": 0.5,
            "status": string_or_none(idea.status) or "active",
            "resource": None,
            "notes": string_or_none(idea.notes) or "",
            "path": f"tasks/tasks.json#ideas/{idea.id}",
        }

    def task_record(self, task: Any) -> SearchRow:
        created_at = str(task.created_at or "")
        updated_at = str(getattr(task, "updated_at", "") or "")
        return {
            "root": "tasks",
            "type": "Task",
            "title": string_or_none(task.title) or task.id,
            "domain": None,
            "topic": None,
            "platform": None,
            "date": created_at[:10],
            "published_at": "",
            "collected_at": created_at,
            "updated_at": updated_at,
            "deleted_at": "",
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
        presenter = ExternalIndexedItemPresenter(ref, item)
        reference_fields = presenter.search_reference_fields()
        return cast(
            SearchRow,
            {
                "root": "mounts",
                "type": "Mounted Item",
                "title": presenter.title,
                "domain": None,
                "topic": None,
                "platform": None,
                "date": frontmatter_date(item),
                "published_at": _first_date(item, "published_at", "published_date", "date"),
                "collected_at": _first_date(item, "indexed_at", "created_at", "timestamp"),
                "updated_at": _first_date(item, "updated_at", "modified_at", "indexed_at"),
                "deleted_at": _first_date(item, "deleted_at"),
                "tags": value_list(item.get("tags")),
                "confidence": 0.5,
                "status": string_or_none(item.get("status")) or "active",
                "resource": string_or_none(item.get("relative_path")) or None,
                "notes": presenter.safe_text(),
                "path": ref.path,
                **reference_fields,
            },
        )

    def connector_item(self, connector_id: str, item: dict[str, Any]) -> SearchRow:
        rel = str(item.get("relative_path") or "")
        ref = ExternalItemReference.connector(connector_id, rel)
        presenter = ExternalIndexedItemPresenter(ref, item)
        item_type = string_or_none(item.get("type")) or "Connector Item"
        reference_fields = presenter.search_reference_fields()
        row = cast(
            SearchRow,
            {
                "root": "connectors",
                "type": item_type,
                "title": presenter.title,
                "domain": string_or_none(item.get("account")),
                "topic": string_or_none(item.get("folder_path")),
                "platform": connector_id,
                "date": frontmatter_date(item),
                "published_at": _first_date(item, "published_at", "published_date", "date"),
                "collected_at": _first_date(
                    item,
                    "indexed_at",
                    "created_at",
                    "date_added",
                    "timestamp",
                ),
                "updated_at": _first_date(item, "updated_at", "date_modified", "indexed_at"),
                "deleted_at": _first_date(item, "deleted_at"),
                "tags": value_list(item.get("tags")),
                "confidence": 0.5,
                "status": string_or_none(item.get("status")) or "active",
                "resource": string_or_none(item.get("resource")) or None,
                "notes": presenter.safe_text(),
                "path": ref.path,
                **reference_fields,
            },
        )
        if presenter.is_secret_like():
            row["redacted"] = True
        quality = presenter.information_quality()
        if quality:
            row["information_quality"] = quality
        return row


def _deduplicated_search_text(parts: list[str]) -> str:
    rows: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for line in part.splitlines() or [part]:
            cleaned = line.strip()
            if not cleaned:
                continue
            key = " ".join(cleaned.casefold().split())
            if not key or key in seen:
                continue
            rows.append(cleaned)
            seen.add(key)
    return "\n".join(rows)


def _first_date(mapping: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if value:
            return str(value)
    return ""
