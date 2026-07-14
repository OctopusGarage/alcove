from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from alcove.external_index import ExternalIndexItem, ExternalIndexStore, ExternalItemReference
from alcove.external_presentation import ExternalIndexedItemPresenter
from alcove.runtime import AlcoveRuntime
from alcove.search_rows import SearchRow, SearchRowBuilder


@dataclass(frozen=True)
class ExternalResolvedItem:
    ref: ExternalItemReference
    item: ExternalIndexItem

    @property
    def presenter(self) -> ExternalIndexedItemPresenter:
        return ExternalIndexedItemPresenter(self.ref, self.item)

    def search_row(self, rows: SearchRowBuilder) -> SearchRow:
        if self.ref.kind == "connector":
            row = dict(rows.connector_item(self.ref.source_id, self.item))
        else:
            row = dict(rows.mount_item(self.item))
        row.update(self.context_fields())
        return row  # type: ignore[return-value]

    def context_fields(self) -> dict[str, Any]:
        fields: dict[str, Any] = {}
        for key in (
            "language",
            "stars",
            "updated_at",
            "connector_name",
            "source_id",
            "account",
            "folder_path",
            "mount_name",
            "mount_type",
        ):
            if key in self.item:
                fields[key] = self.item[key]
        return fields


class ExternalItemResolver:
    """Resolve external item identity once for search, fetch, and link adapters."""

    def __init__(self, runtime: AlcoveRuntime) -> None:
        self.runtime = runtime
        self.connector_store = ExternalIndexStore(runtime.connectors_root)
        self.mount_store = ExternalIndexStore(runtime.mounts_root)

    def resolve(self, item_path: str) -> ExternalResolvedItem:
        ref = ExternalItemReference.parse_optional(item_path)
        if ref is None:
            ref = self._resolve_connector_alias(item_path)
        item = self._find(ref)
        if item is None:
            raise FileNotFoundError(f"External indexed item not found: {item_path}")
        return ExternalResolvedItem(ref=ref, item=item)

    def resolve_connector(self, item_path: str) -> ExternalResolvedItem:
        resolved = self.resolve(item_path)
        if resolved.ref.kind != "connector":
            raise ValueError(
                "Connector item path must look like connectors/<connector-id>#<relative-path> "
                "or <connector-id>/<display-slug>"
            )
        return resolved

    def _find(self, ref: ExternalItemReference) -> ExternalIndexItem | None:
        if ref.kind == "connector":
            return self.connector_store.find_item(ref)
        return self.mount_store.find_item(ref)

    def _resolve_connector_alias(self, item_path: str) -> ExternalItemReference:
        connector_id, separator, alias = item_path.partition("/")
        if not separator or not connector_id or not alias:
            raise ValueError(
                "External item path must look like connectors/<connector-id>#<relative-path>, "
                "mounts/<mount-id>#<relative-path>, or <connector-id>/<display-slug>"
            )
        matches: list[ExternalItemReference] = []
        target = f"{connector_id}/{alias}"
        for dataset in self.connector_store.connector_datasets():
            if dataset.source_id != connector_id:
                continue
            for item in dataset.items:
                relative_path = str(item.get("relative_path") or "")
                ref = ExternalItemReference.connector(connector_id, relative_path)
                if ExternalIndexedItemPresenter(ref, item).display_id() == target:
                    matches.append(ref)
        if len(matches) > 1:
            raise FileExistsError(
                f"Connector item alias is ambiguous: {connector_id}/{alias}; "
                "use connectors/<connector-id>#<relative-path> instead"
            )
        if not matches:
            raise FileNotFoundError(f"Connector item alias not found: {item_path}")
        return matches[0]
