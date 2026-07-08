from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path

from alcove.home import AlcoveHome
from alcove.markdown import normalize_slug
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
        self.workspace = workspace
        self.home = home
        if home is None and workspace is None:
            home = AlcoveHome.init()
            self.home = home
        self.global_home = home is not None
        self.mounts_root = home.paths().mounts if home is not None else workspace.paths().mounts
        self.indexes_root = home.paths().mount_indexes if home is not None else self.mounts_root
        self.taxonomy = (
            load_taxonomy(workspace.paths().knowledge)
            if workspace
            else load_taxonomy(self.mounts_root)
        )
        self.store_path = self.mounts_root / "mounts.json"
        self.index_path = self.mounts_root / "index.json"

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
        for mount in mounts:
            mount_items, mount_skipped = self._scan_mount(mount)
            items.extend(mount_items)
            skipped += mount_skipped
        self._save_index(items, mounts)
        return {
            "mount": asdict(mounts[0]) if len(mounts) == 1 else None,
            "scanned": len(items),
            "skipped": skipped,
            "items": items,
        }

    def index_items(self) -> list[dict]:
        indexes_dir = self.mounts_root / "indexes"
        if indexes_dir.is_dir():
            rows: list[dict] = []
            for path in sorted(indexes_dir.glob("*.json")):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue
                items = data.get("items") if isinstance(data, dict) else []
                rows.extend(item for item in items if isinstance(item, dict))
            return rows
        if not self.index_path.is_file():
            return []
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        items = data.get("items") if isinstance(data, dict) else []
        return [item for item in items if isinstance(item, dict)]

    def _scan_mount(self, mount: Mount) -> tuple[list[dict], int]:
        root = Path(mount.path)
        items: list[dict] = []
        skipped = 0
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
            if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
                continue
            if not path.is_file():
                continue
            if path.suffix.lower() not in TEXT_EXTENSIONS:
                skipped += 1
                continue
            if path.stat().st_size > MAX_INDEXED_TEXT_BYTES:
                skipped += 1
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            rel = path.relative_to(root).as_posix()
            items.append(
                {
                    "mount_id": mount.id,
                    "mount_name": mount.name,
                    "mount_type": mount.type,
                    "path": str(path),
                    "relative_path": rel,
                    "title": self._title(text, path),
                    "text": text[:4000],
                    "tags": mount.tags,
                    "status": mount.status,
                    "indexed_at": now_iso(),
                }
            )
        return items, skipped

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
            self.indexes_root.mkdir(parents=True, exist_ok=True)
            by_mount: dict[str, list[dict]] = {}
            for item in items:
                by_mount.setdefault(str(item.get("mount_id") or ""), []).append(item)
            for mount in mounts:
                mount_items = by_mount.get(mount.id, [])
                (self.indexes_root / f"{mount.id}.json").write_text(
                    json.dumps({"items": mount_items}, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            return
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(
            json.dumps({"items": items}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

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
