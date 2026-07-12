from __future__ import annotations

from pathlib import Path
from typing import Any

from alcove.derived_okf import (
    DerivedOkfDocument,
    DerivedOkfWriter,
    stable_derived_item_filename,
    stable_slug_filename,
)
from alcove.markdown import MarkdownDoc


CONNECTOR_INDEX_SCHEMA = "okf/connector-index/v1"
CONNECTOR_ITEM_SCHEMA = "okf/connector-item/v1"
CONNECTOR_SOURCE_SCHEMA = "okf/connector-source/v1"


def write_connector_okf_index(
    *,
    connector_dir: Path,
    connector_id: str,
    connector_name: str,
    items: list[dict[str, Any]],
    generated_at: str,
) -> None:
    okf_root = connector_dir / "okf"
    writer = DerivedOkfWriter()
    writer.write_item_docs(
        okf_root / "items",
        [
            DerivedOkfDocument(
                key=_item_key(item),
                doc=_item_doc(connector_id, connector_name, item),
            )
            for item in items
        ],
    )
    writer.write_doc(
        okf_root / "index.md",
        _index_doc(
            connector_id=connector_id,
            connector_name=connector_name,
            items=items,
            generated_at=generated_at,
        ),
    )


def write_connector_okf_sources(
    *,
    connector_dir: Path,
    connector_id: str,
    connector_name: str,
    sources: list[dict[str, Any]],
    generated_at: str,
) -> None:
    source_dir = connector_dir / "okf" / "sources"
    DerivedOkfWriter().write_named_docs(
        source_dir,
        [
            DerivedOkfDocument(
                key=str(source.get("id") or ""),
                doc=_source_doc(
                    connector_id=connector_id,
                    connector_name=connector_name,
                    source=source,
                    generated_at=generated_at,
                ),
            )
            for source in sources
            if str(source.get("id") or "")
        ],
        filename_for=stable_slug_filename,
    )


def _index_doc(
    *,
    connector_id: str,
    connector_name: str,
    items: list[dict[str, Any]],
    generated_at: str,
) -> MarkdownDoc:
    body_lines = [
        f"# {connector_name}",
        "",
        "## Connector",
        "",
        f"- ID: `{connector_id}`",
        f"- Items: {len(items)}",
        "",
        "## Items",
        "",
    ]
    for item in items:
        title = str(item.get("title") or item.get("relative_path") or "")
        relative_path = str(item.get("relative_path") or "")
        body_lines.append(
            f"- [{title}](items/{stable_derived_item_filename(_item_key(item))}) - `{relative_path}`"
        )
    return MarkdownDoc(
        frontmatter={
            "type": "Connector Index",
            "schema": CONNECTOR_INDEX_SCHEMA,
            "title": connector_name,
            "connector_id": connector_id,
            "status": "active",
            "item_count": len(items),
            "generated_at": generated_at,
        },
        body="\n".join(body_lines),
    )


def _source_doc(
    *,
    connector_id: str,
    connector_name: str,
    source: dict[str, Any],
    generated_at: str,
) -> MarkdownDoc:
    source_id = str(source.get("id") or "")
    refresh = source.get("refresh") if isinstance(source.get("refresh"), dict) else {}
    item_count = _int_value(refresh.get("item_count"), 0)
    source_value = str(source.get("source") or source.get("username") or "")
    status = str(refresh.get("status") or source.get("status") or "active")
    body = "\n".join(
        [
            f"# {connector_name}: {source_id}",
            "",
            "## Source",
            "",
            f"- Connector: `{connector_id}`",
            f"- Source ID: `{source_id}`",
            f"- Source: `{source_value}`",
            f"- Items: {item_count}",
            f"- Status: `{status}`",
            "",
            "## Refresh",
            "",
            f"- Last checked: `{refresh.get('last_checked_at') or ''}`",
            f"- Last changed: `{refresh.get('last_changed_at') or ''}`",
            f"- Last error: `{refresh.get('last_error') or ''}`",
        ]
    )
    return MarkdownDoc(
        frontmatter={
            "type": "Connector Source",
            "schema": CONNECTOR_SOURCE_SCHEMA,
            "title": f"{connector_name}: {source_id}",
            "connector_id": connector_id,
            "connector_name": connector_name,
            "source_id": source_id,
            "source": source_value,
            "tags": list(source.get("tags") or []),
            "status": status,
            "item_count": item_count,
            "generated_at": generated_at,
        },
        body=body,
    )


def _item_doc(connector_id: str, connector_name: str, item: dict[str, Any]) -> MarkdownDoc:
    title = str(item.get("title") or item.get("relative_path") or "Connector Item")
    relative_path = str(item.get("relative_path") or "")
    resource = str(item.get("resource") or item.get("path") or "")
    text = str(item.get("text") or "")
    body = "\n".join(
        [
            f"# {title}",
            "",
            "## Source",
            "",
            f"- Connector: `{connector_id}`",
            f"- Relative path: `{relative_path}`",
            f"- Resource: `{resource}`",
            "",
            "## Content",
            "",
            text,
        ]
    )
    frontmatter = {
        "type": str(item.get("type") or "Connector Item"),
        "schema": CONNECTOR_ITEM_SCHEMA,
        "title": title,
        "connector_id": connector_id,
        "connector_name": connector_name,
        "resource": resource,
        "relative_path": relative_path,
        "tags": list(item.get("tags") or []),
        "status": str(item.get("status") or "active"),
        "indexed_at": str(item.get("indexed_at") or ""),
    }
    for key in ("account", "folder_path", "source_id", "file_size", "file_mtime_ns"):
        if key in item:
            frontmatter[key] = item.get(key)
    return MarkdownDoc(frontmatter=frontmatter, body=body)


def _item_key(item: dict[str, Any]) -> str:
    return str(item.get("relative_path") or item.get("title") or "item")


def _int_value(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
