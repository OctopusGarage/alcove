from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path

from alcove.external_index import ExternalIndexItemFactory, ExternalIndexStore
from alcove.home import AlcoveHome
from alcove.markdown import normalize_slug
from alcove.runtime import AlcoveRuntime
from alcove.taxonomy import load_taxonomy, normalize_tag
from alcove.workspace import Workspace


TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".rst"}
SKIP_DIRS = {".git", ".hg", ".svn", ".venv", "node_modules", "__pycache__"}
MAX_INDEXED_TEXT_BYTES = 1_000_000


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class AddMountRequest:
    path: str
    name: str = ""
    mount_type: str = "local-folder"
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Mount:
    id: str
    name: str
    type: str
    path: str
    tags: list[str]
    status: str
    created_at: str
    updated_at: str


class MountsModule:
    def __init__(self, workspace: Workspace | None = None, home: AlcoveHome | None = None) -> None:
        self.runtime = AlcoveRuntime.from_modules(workspace=workspace, home=home)
        self.workspace = self.runtime.workspace
        self.home = self.runtime.home
        self.global_home = self.runtime.home is not None
        self.mounts_root = self.runtime.mounts_root
        self.indexes_root = self.runtime.mount_indexes_root
        taxonomy_root = self.runtime.knowledge_root if self.workspace else self.mounts_root
        self.taxonomy = load_taxonomy(taxonomy_root)
        self.store_path = self.mounts_root / "mounts.json"
        self.index_path = self.mounts_root / "index.json"
        self.index_store = ExternalIndexStore(self.mounts_root)

    def add(self, request: AddMountRequest) -> Mount:
        data = self._load_mounts()
        source_path = Path(request.path).expanduser().resolve()
        if not source_path.is_dir():
            raise FileNotFoundError(f"Mount path is not a directory: {request.path}")
        mount_type = normalize_slug(request.mount_type)
        if mount_type not in {"local-folder", "git-repo-local"}:
            raise ValueError(f"Unsupported mount type: {request.mount_type}")
        if mount_type == "git-repo-local" and not (source_path / ".git").exists():
            raise ValueError(f"Mount path is not a local git repository: {source_path}")
        timestamp = now_iso()
        name = request.name or source_path.name
        mount = Mount(
            id=self._unique_id(name, [item["id"] for item in data["mounts"]]),
            name=name,
            type=mount_type,
            path=str(source_path),
            tags=self._normalize_tags(request.tags),
            status="active",
            created_at=timestamp,
            updated_at=timestamp,
        )
        data["mounts"].append(asdict(mount))
        self._save_mounts(data)
        return mount

    def list(self, status: str = "active") -> list[Mount]:
        return [
            self._mount(item)
            for item in self._load_mounts()["mounts"]
            if not status or item.get("status") == status
        ]

    def scan(self, mount_id: str | None = None) -> dict:
        mounts = self.list()
        if mount_id:
            mounts = [mount for mount in mounts if mount.id == normalize_slug(mount_id)]
            if not mounts:
                raise FileNotFoundError(f"Mount not found: {mount_id}")
        items: list[dict] = []
        skipped = 0
        reused = 0
        for mount in mounts:
            mount_items, mount_skipped, mount_reused = self._scan_mount(mount)
            items.extend(mount_items)
            skipped += mount_skipped
            reused += mount_reused
        self._save_index(items, mounts)
        return {
            "mount": asdict(mounts[0]) if len(mounts) == 1 else None,
            "scanned": len(items),
            "skipped": skipped,
            "reused": reused,
            "items": items,
        }

    def index_items(self) -> list[dict]:
        rows: list[dict] = []
        for dataset in self.index_store.mount_datasets():
            rows.extend(dataset.items)
        return rows

    def _scan_mount(self, mount: Mount) -> tuple[list[dict], int, int]:
        root = Path(mount.path)
        existing = self._existing_items_by_path(mount)
        items: list[dict] = []
        skipped = 0
        reused = 0
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
            if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
                continue
            if not path.is_file():
                continue
            stat = path.stat()
            if path.suffix.lower() not in TEXT_EXTENSIONS:
                skipped += 1
                continue
            if stat.st_size > MAX_INDEXED_TEXT_BYTES:
                skipped += 1
                continue
            rel = path.relative_to(root).as_posix()
            previous = existing.get(rel)
            if self._unchanged(previous, stat.st_size, stat.st_mtime_ns):
                items.append(
                    {
                        **previous,
                        "mount_name": mount.name,
                        "mount_type": mount.type,
                        "path": str(path),
                        "tags": mount.tags,
                        "status": mount.status,
                    }
                )
                reused += 1
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            items.append(
                ExternalIndexItemFactory.mounted_item(
                    mount_id=mount.id,
                    mount_name=mount.name,
                    mount_type=mount.type,
                    path=path,
                    relative_path=rel,
                    title=self._title(text, path),
                    text=text,
                    tags=mount.tags,
                    status=mount.status,
                    indexed_at=now_iso(),
                    file_size=stat.st_size,
                    file_mtime_ns=stat.st_mtime_ns,
                )
            )
        return items, skipped, reused

    def _existing_items_by_path(self, mount: Mount) -> dict[str, dict]:
        items: dict[str, dict] = {}
        for dataset in self.index_store.mount_datasets():
            if dataset.source_id == mount.id:
                candidates = dataset.items
            else:
                candidates = [
                    item for item in dataset.items if str(item.get("mount_id") or "") == mount.id
                ]
            for item in candidates:
                rel = str(item.get("relative_path") or "")
                if rel:
                    items[rel] = item
        return items

    def _unchanged(self, item: dict | None, file_size: int, file_mtime_ns: int) -> bool:
        if item is None:
            return False
        return item.get("file_size") == file_size and item.get("file_mtime_ns") == file_mtime_ns

    def _load_mounts(self) -> dict[str, list[dict]]:
        if not self.store_path.is_file():
            return {"mounts": []}
        data = json.loads(self.store_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"mounts": []}
        mounts = data.get("mounts")
        return {"mounts": mounts if isinstance(mounts, list) else []}

    def _save_mounts(self, data: dict[str, list[dict]]) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _save_index(self, items: list[dict], mounts: list[Mount]) -> None:
        if self.global_home:
            by_mount: dict[str, list[dict]] = {}
            for item in items:
                by_mount.setdefault(str(item.get("mount_id") or ""), []).append(item)
            ExternalIndexStore(self.mounts_root).write_mount_indexes(
                {mount.id: by_mount.get(mount.id, []) for mount in mounts}
            )
            return
        self.index_store.write_mount_index(items)

    def _mount(self, item: dict) -> Mount:
        return Mount(
            id=str(item.get("id") or ""),
            name=str(item.get("name") or ""),
            type=str(item.get("type") or "local-folder"),
            path=str(item.get("path") or ""),
            tags=[str(tag) for tag in self._list(item.get("tags"))],
            status=str(item.get("status") or "active"),
            created_at=str(item.get("created_at") or ""),
            updated_at=str(item.get("updated_at") or ""),
        )

    def _unique_id(self, name: str, existing: list[str]) -> str:
        slug = normalize_slug(name)
        if slug not in existing:
            return slug
        counter = 2
        while f"{slug}-{counter}" in existing:
            counter += 1
        return f"{slug}-{counter}"

    def _normalize_tags(self, tags: list[str]) -> list[str]:
        normalized = {normalize_tag(tag, self.taxonomy) for tag in tags}
        return sorted(tag for tag in normalized if tag)

    def _title(self, text: str, path: Path) -> str:
        for line in text.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return path.stem

    def _list(self, value: object) -> list:
        return value if isinstance(value, list) else []
