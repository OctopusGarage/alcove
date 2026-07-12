from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from alcove.paths import compact_user_path


ExternalIndexItem = dict[str, Any]
ExternalItemKind = Literal["connector", "mount"]


class ExternalIndexPayload(TypedDict, total=False):
    schema_version: int
    connector: str
    export_file: str
    indexed_at: str
    items: list[ExternalIndexItem]


@dataclass(frozen=True)
class ExternalIndexDataset:
    source_id: str
    path: Path
    payload: ExternalIndexPayload

    @property
    def items(self) -> list[ExternalIndexItem]:
        value = self.payload.get("items")
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict) and _valid_index_item(item)]


@dataclass(frozen=True)
class ExternalItemReference:
    kind: ExternalItemKind
    source_id: str
    relative_path: str

    @classmethod
    def connector(cls, connector_id: str, relative_path: str) -> "ExternalItemReference":
        return cls("connector", connector_id, relative_path)

    @classmethod
    def mount(cls, mount_id: str, relative_path: str) -> "ExternalItemReference":
        return cls("mount", mount_id, relative_path)

    @classmethod
    def parse(cls, item_path: str) -> "ExternalItemReference":
        root, separator, relative_path = item_path.partition("#")
        if not separator or not relative_path:
            raise ValueError(cls._format_error())
        if root.startswith("connectors/"):
            source_id = root.removeprefix("connectors/")
            if source_id:
                return cls.connector(source_id, relative_path)
        if root.startswith("mounts/"):
            source_id = root.removeprefix("mounts/")
            if source_id:
                return cls.mount(source_id, relative_path)
        raise ValueError(cls._format_error())

    @classmethod
    def parse_connector(cls, item_path: str) -> "ExternalItemReference":
        ref = cls.parse(item_path)
        if ref.kind != "connector":
            raise ValueError(
                "Connector item path must look like connectors/<connector-id>#<relative-path>"
            )
        return ref

    @classmethod
    def parse_optional(cls, item_path: str) -> "ExternalItemReference | None":
        try:
            return cls.parse(item_path)
        except ValueError:
            return None

    @property
    def path(self) -> str:
        root = "connectors" if self.kind == "connector" else "mounts"
        return f"{root}/{self.source_id}#{self.relative_path}"

    @staticmethod
    def _format_error() -> str:
        return (
            "External item path must look like "
            "connectors/<connector-id>#<relative-path> or mounts/<mount-id>#<relative-path>"
        )


class ExternalIndexStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def read_file(self, path: Path) -> ExternalIndexPayload | None:
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        return cast(ExternalIndexPayload, data) if isinstance(data, dict) else None

    def write_file(self, path: Path, payload: ExternalIndexPayload) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def connector_datasets(self) -> list[ExternalIndexDataset]:
        if not self.root.is_dir():
            return []
        datasets: list[ExternalIndexDataset] = []
        for path in sorted(self.root.glob("*/index.json"), key=lambda item: item.as_posix()):
            payload = self.read_file(path)
            if payload is None:
                continue
            datasets.append(
                ExternalIndexDataset(
                    source_id=str(payload.get("connector") or path.parent.name),
                    path=path,
                    payload=payload,
                )
            )
        return datasets

    def mount_datasets(self) -> list[ExternalIndexDataset]:
        indexes_dir = self.root / "indexes"
        if indexes_dir.is_dir():
            datasets: list[ExternalIndexDataset] = []
            for path in sorted(indexes_dir.glob("*.json")):
                payload = self.read_file(path)
                if payload is None:
                    continue
                datasets.append(
                    ExternalIndexDataset(source_id=path.stem, path=path, payload=payload)
                )
            return datasets
        payload = self.read_file(self.root / "index.json")
        if payload is None:
            return []
        return [
            ExternalIndexDataset(source_id="legacy", path=self.root / "index.json", payload=payload)
        ]

    def write_connector_index(self, connector_id: str, payload: ExternalIndexPayload) -> Path:
        path = self.root / connector_id / "index.json"
        self.write_file(path, payload)
        return path

    def write_mount_index(self, items: list[ExternalIndexItem]) -> Path:
        path = self.root / "index.json"
        self.write_file(path, {"items": items})
        return path

    def write_mount_indexes(self, items_by_mount: dict[str, list[ExternalIndexItem]]) -> list[Path]:
        index_root = self.root / "indexes"
        paths: list[Path] = []
        for mount_id, items in items_by_mount.items():
            path = index_root / f"{mount_id}.json"
            self.write_file(path, {"items": items})
            paths.append(path)
        return paths

    def find_connector_item(
        self, connector_id: str, relative_path: str
    ) -> ExternalIndexItem | None:
        return self.find_item(ExternalItemReference.connector(connector_id, relative_path))

    def find_mount_item(self, mount_id: str, relative_path: str) -> ExternalIndexItem | None:
        return self.find_item(ExternalItemReference.mount(mount_id, relative_path))

    def find_item(self, ref: ExternalItemReference) -> ExternalIndexItem | None:
        if ref.kind == "connector":
            return self._find_connector_item(ref)
        return self._find_mount_item(ref)

    def _find_connector_item(self, ref: ExternalItemReference) -> ExternalIndexItem | None:
        for dataset in self.connector_datasets():
            if dataset.source_id != ref.source_id:
                continue
            item = self._find_item(dataset.items, ref.relative_path)
            if item is not None:
                return item
            return self._find_unique_connector_item_by_legacy_path(
                dataset.items,
                ref.relative_path,
            )
        return None

    def _find_mount_item(self, ref: ExternalItemReference) -> ExternalIndexItem | None:
        for dataset in self.mount_datasets():
            if dataset.source_id == ref.source_id:
                return self._find_item(dataset.items, ref.relative_path)
            legacy_item = self._find_mount_item_in_legacy_dataset(
                dataset.items,
                ref.source_id,
                ref.relative_path,
            )
            if legacy_item is not None:
                return legacy_item
        return None

    def _find_item(
        self,
        items: list[ExternalIndexItem],
        relative_path: str,
    ) -> ExternalIndexItem | None:
        for item in items:
            if str(item.get("relative_path") or "") == relative_path:
                return item
        return None

    def _find_unique_connector_item_by_legacy_path(
        self,
        items: list[ExternalIndexItem],
        relative_path: str,
    ) -> ExternalIndexItem | None:
        suffix = f"/{relative_path}"
        matches = [
            item
            for item in items
            if str(item.get("source_id") or "")
            and str(item.get("relative_path") or "").endswith(suffix)
        ]
        if len(matches) == 1:
            return matches[0]
        return None

    def _find_mount_item_in_legacy_dataset(
        self,
        items: list[ExternalIndexItem],
        mount_id: str,
        relative_path: str,
    ) -> ExternalIndexItem | None:
        for item in items:
            if str(item.get("mount_id") or "") != mount_id:
                continue
            if str(item.get("relative_path") or "") == relative_path:
                return item
        return None


def _valid_index_item(item: ExternalIndexItem) -> bool:
    return bool(str(item.get("relative_path") or "").strip()) and bool(
        str(item.get("title") or "").strip()
    )


class ExternalIndexItemFactory:
    @staticmethod
    def mounted_item(
        *,
        mount_id: str,
        mount_name: str,
        mount_type: str,
        path: Path,
        relative_path: str,
        title: str,
        text: str,
        tags: list[str],
        status: str,
        indexed_at: str,
        file_size: int | None = None,
        file_mtime_ns: int | None = None,
    ) -> ExternalIndexItem:
        item: ExternalIndexItem = {
            "source_kind": "mount",
            "mount_id": mount_id,
            "mount_name": mount_name,
            "mount_type": mount_type,
            "path": compact_user_path(path),
            "relative_path": relative_path,
            "title": title,
            "text": text[:4000],
            "tags": tags,
            "status": status,
            "indexed_at": indexed_at,
        }
        if file_size is not None:
            item["file_size"] = file_size
        if file_mtime_ns is not None:
            item["file_mtime_ns"] = file_mtime_ns
        return item

    @staticmethod
    def connector_item(
        *,
        connector_id: str,
        connector_name: str,
        item_type: str,
        title: str,
        relative_path: str,
        text: str,
        tags: list[str],
        status: str,
        indexed_at: str,
        path: str = "",
        resource: str = "",
        account: str = "",
        folder_path: str = "",
        extra: dict[str, Any] | None = None,
    ) -> ExternalIndexItem:
        item = {
            "source_kind": "connector",
            "connector": connector_id,
            "connector_name": connector_name,
            "type": item_type,
            "title": title,
            "account": account,
            "folder_path": folder_path,
            "path": compact_user_path(path) if path else "",
            "resource": resource,
            "relative_path": relative_path,
            "text": text[:4000],
            "tags": tags,
            "status": status,
            "indexed_at": indexed_at,
        }
        if extra:
            item.update(extra)
        return item
