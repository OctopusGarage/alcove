from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from fnmatch import fnmatch
import json
from pathlib import Path

from alcove.derived_okf import DerivedOkfDocument, DerivedOkfWriter, stable_derived_item_filename
from alcove.external_index import ExternalIndexItemFactory, ExternalIndexStore
from alcove.home import AlcoveHome
from alcove.markdown import MarkdownDoc, normalize_slug
from alcove.paths import compact_user_path
from alcove.runtime import AlcoveRuntime
from alcove.taxonomy import load_taxonomy, normalize_tag
from alcove.workspace import Workspace


TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".rst"}
SKIP_DIRS = {".git", ".hg", ".svn", ".venv", "node_modules", "__pycache__"}
MAX_INDEXED_TEXT_BYTES = 1_000_000
MOUNT_INDEX_SCHEMA = "okf/mount-index/v1"
MOUNT_ITEM_SCHEMA = "okf/mounted-item/v1"
RAW_INCLUDE_PATTERNS = [
    "*.md",
    "*.markdown",
    "*.txt",
    "*.rst",
    "**/*.md",
    "**/*.markdown",
    "**/*.txt",
    "**/*.rst",
]
DEFAULT_EXCLUDE_PATTERNS = [
    ".git/**",
    ".hg/**",
    ".svn/**",
    ".venv/**",
    "node_modules/**",
    "__pycache__/**",
]
PROFILE_POLICIES = {
    "raw": {
        "include": RAW_INCLUDE_PATTERNS,
        "exclude": DEFAULT_EXCLUDE_PATTERNS,
    },
    "notes": {
        "include": RAW_INCLUDE_PATTERNS,
        "exclude": [
            *DEFAULT_EXCLUDE_PATTERNS,
            "**/_build/**",
            "**/dist/**",
            "**/build/**",
            "**/coverage/**",
        ],
    },
    "docs": {
        "include": [
            "README*",
            "CHANGELOG*",
            "CONTRIBUTING*",
            "LICENSE*",
            "docs/**",
            "doc/**",
            "guides/**",
            "guide/**",
            "wiki/**",
            "adr/**",
            "adrs/**",
            "rfcs/**",
            "book/**/*.md",
            "book/**/*.txt",
        ],
        "exclude": [
            *DEFAULT_EXCLUDE_PATTERNS,
            ".agents/**",
            ".claude/**",
            "docs/superpowers/**",
            "src/**",
            "source/**",
            "**/_build/**",
            "**/_book/**",
            "**/dist/**",
            "**/build/**",
            "**/coverage/**",
            "archived-*/**",
        ],
    },
    "site": {
        "include": [
            "README*",
            "MAINTENANCE.md",
            "llms*.txt",
            "content/**",
            "posts/**",
            "notes/**",
            "docs/**",
        ],
        "exclude": [
            *DEFAULT_EXCLUDE_PATTERNS,
            ".agents/**",
            ".claude/**",
            "vendor/**",
            "tests/**",
            "**/_site/**",
            "**/.next/**",
            "**/dist/**",
            "**/build/**",
            "**/coverage/**",
        ],
    },
    "capture-bundles": {
        "include": [
            "**/post.md",
            "**/summary.md",
            "**/raw/rendered.txt",
            "_urls.txt",
            "**/_urls.txt",
        ],
        "exclude": DEFAULT_EXCLUDE_PATTERNS,
    },
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class MountIndexPolicy:
    profile: str = "raw"
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    max_file_size_kb: int = MAX_INDEXED_TEXT_BYTES // 1024

    def resolve(self) -> "ResolvedMountIndexPolicy":
        profile = normalize_slug(self.profile or "raw")
        if profile not in PROFILE_POLICIES:
            raise ValueError(f"Unsupported mount index profile: {self.profile}")
        defaults = PROFILE_POLICIES[profile]
        include = self.include or list(defaults["include"])
        exclude = [*defaults["exclude"], *self.exclude]
        max_bytes = max(1, int(self.max_file_size_kb)) * 1024
        return ResolvedMountIndexPolicy(
            profile=profile,
            include=_dedupe_patterns(include),
            exclude=_dedupe_patterns(exclude),
            max_file_size_bytes=max_bytes,
        )

    def as_config(self) -> dict:
        resolved = self.resolve()
        return resolved.as_public_dict()


@dataclass(frozen=True)
class ResolvedMountIndexPolicy:
    profile: str
    include: list[str]
    exclude: list[str]
    max_file_size_bytes: int

    def as_public_dict(self) -> dict:
        return {
            "profile": self.profile,
            "include": self.include,
            "exclude": self.exclude,
            "max_file_size_kb": self.max_file_size_bytes // 1024,
        }

    def decision(self, relative_path: str, suffix: str, file_size: int) -> str:
        if suffix.lower() not in TEXT_EXTENSIONS:
            return "unsupported_extension"
        if file_size > self.max_file_size_bytes:
            return "too_large"
        if _matches_any(relative_path, self.exclude):
            return "excluded"
        if not _matches_any(relative_path, self.include):
            return "not_included"
        return "indexed"


@dataclass(frozen=True)
class AddMountRequest:
    path: str
    name: str = ""
    mount_type: str = "local-folder"
    tags: list[str] = field(default_factory=list)
    index_policy: MountIndexPolicy = field(default_factory=MountIndexPolicy)


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
    index_policy: MountIndexPolicy = field(default_factory=MountIndexPolicy)


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
        self.okf_root = self.mounts_root / "okf"
        self.okf_writer = DerivedOkfWriter()

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
        index_policy = self._index_policy(request.index_policy.as_config())
        mount = Mount(
            id=self._unique_id(name, [item["id"] for item in data["mounts"]]),
            name=name,
            type=mount_type,
            path=compact_user_path(source_path),
            tags=self._normalize_tags(request.tags),
            status="active",
            created_at=timestamp,
            updated_at=timestamp,
            index_policy=index_policy,
        )
        data["mounts"].append(self._mount_record(mount))
        self._save_mounts(data)
        return mount

    def list(self, status: str = "active") -> list[Mount]:
        return [
            self._mount(item)
            for item in self._load_mounts()["mounts"]
            if not status or item.get("status") == status
        ]

    def update_policy(self, mount_id: str, policy: MountIndexPolicy) -> Mount:
        data = self._load_mounts()
        normalized_id = normalize_slug(mount_id)
        timestamp = now_iso()
        for index, item in enumerate(data["mounts"]):
            if str(item.get("id") or "") != normalized_id:
                continue
            item["index_policy"] = self._merged_policy(
                self._mount(item).index_policy, policy
            ).as_config()
            item["updated_at"] = timestamp
            data["mounts"][index] = item
            self._save_mounts(data)
            return self._mount(item)
        raise FileNotFoundError(f"Mount not found: {mount_id}")

    def scan(
        self,
        mount_id: str | None = None,
        include_diagnostics: bool = False,
        dry_run: bool = False,
    ) -> dict:
        mounts = self.list()
        if mount_id:
            mounts = [mount for mount in mounts if mount.id == normalize_slug(mount_id)]
            if not mounts:
                raise FileNotFoundError(f"Mount not found: {mount_id}")
        items: list[dict] = []
        skipped = 0
        reused = 0
        skip_reasons: dict[str, int] = {}
        policies: dict[str, dict] = {}
        for mount in mounts:
            mount_items, mount_skipped, mount_reused, mount_skip_reasons = self._scan_mount(mount)
            items.extend(mount_items)
            skipped += mount_skipped
            reused += mount_reused
            policies[mount.id] = mount.index_policy.resolve().as_public_dict()
            for reason, count in mount_skip_reasons.items():
                skip_reasons[reason] = skip_reasons.get(reason, 0) + count
        if not dry_run:
            self._save_index(items, mounts)
        return {
            "mount": self._mount_record(mounts[0]) if len(mounts) == 1 else None,
            "scanned": len(items),
            "skipped": skipped,
            "reused": reused,
            "dry_run": dry_run,
            "policy": policies[mounts[0].id] if len(mounts) == 1 else None,
            "policies": policies,
            "skip_reasons": skip_reasons,
            "items": [
                self._public_item(item, include_diagnostics=include_diagnostics) for item in items
            ],
        }

    def index_items(self) -> list[dict]:
        rows: list[dict] = []
        for dataset in self.index_store.mount_datasets():
            rows.extend(dataset.items)
        return rows

    def _scan_mount(self, mount: Mount) -> tuple[list[dict], int, int, dict[str, int]]:
        root = Path(mount.path).expanduser()
        existing = self._existing_items_by_path(mount)
        policy = mount.index_policy.resolve()
        items: list[dict] = []
        skipped = 0
        reused = 0
        skip_reasons: dict[str, int] = {}
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
            if not path.is_file():
                continue
            stat = path.stat()
            rel = path.relative_to(root).as_posix()
            if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
                skipped += 1
                skip_reasons["excluded"] = skip_reasons.get("excluded", 0) + 1
                continue
            decision = policy.decision(rel, path.suffix, stat.st_size)
            if decision != "indexed":
                skipped += 1
                skip_reasons[decision] = skip_reasons.get(decision, 0) + 1
                continue
            previous = existing.get(rel)
            if self._unchanged(previous, stat.st_size, stat.st_mtime_ns):
                items.append(
                    {
                        **previous,
                        "mount_name": mount.name,
                        "mount_type": mount.type,
                        "path": compact_user_path(path),
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
        return items, skipped, reused, skip_reasons

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

    def _public_item(self, item: dict, include_diagnostics: bool = False) -> dict:
        public = dict(item)
        public.pop("path", None)
        diagnostics = {
            key: public.pop(key)
            for key in ("file_size", "file_mtime_ns")
            if key in public and public.get(key) is not None
        }
        if include_diagnostics and diagnostics:
            public["diagnostics"] = diagnostics
        return public

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
            self._write_okf_indexes(
                {mount.id: by_mount.get(mount.id, []) for mount in mounts}, mounts
            )
            return
        self.index_store.write_mount_index(items)
        by_mount = {}
        for item in items:
            by_mount.setdefault(str(item.get("mount_id") or ""), []).append(item)
        self._write_okf_indexes({mount.id: by_mount.get(mount.id, []) for mount in mounts}, mounts)

    def _write_okf_indexes(
        self, items_by_mount: dict[str, list[dict]], mounts: list[Mount]
    ) -> None:
        for mount in mounts:
            items = items_by_mount.get(mount.id, [])
            mount_dir = self.okf_root / mount.id
            self.okf_writer.write_item_docs(
                mount_dir / "items",
                [
                    DerivedOkfDocument(
                        key=str(item.get("relative_path") or "item"),
                        doc=self._okf_item_doc(mount, item),
                    )
                    for item in items
                ],
            )
            self.okf_writer.write_doc(
                mount_dir / "index.md", self._okf_mount_index_doc(mount, items)
            )

    def _okf_mount_index_doc(self, mount: Mount, items: list[dict]) -> MarkdownDoc:
        policy = mount.index_policy.resolve().as_public_dict()
        include_text = ", ".join(f"`{pattern}`" for pattern in policy["include"]) or "(none)"
        exclude_text = ", ".join(f"`{pattern}`" for pattern in policy["exclude"]) or "(none)"
        body_lines = [
            f"# {mount.name}",
            "",
            "## Mount",
            "",
            f"- ID: `{mount.id}`",
            f"- Type: `{mount.type}`",
            f"- Path: `{mount.path}`",
            f"- Items: {len(items)}",
            "",
            "## Index Policy",
            "",
            f"- Profile: `{policy['profile']}`",
            f"- Include: {include_text}",
            f"- Exclude: {exclude_text}",
            f"- Max file size: {policy['max_file_size_kb']} KB",
            "",
            "## Items",
            "",
        ]
        for item in items:
            title = str(item.get("title") or item.get("relative_path") or "")
            relative_path = str(item.get("relative_path") or "")
            body_lines.append(
                f"- [{title}](items/{stable_derived_item_filename(relative_path)}) - `{relative_path}`"
            )
        return MarkdownDoc(
            frontmatter={
                "type": "Mount Index",
                "schema": MOUNT_INDEX_SCHEMA,
                "title": mount.name,
                "mount_id": mount.id,
                "mount_type": mount.type,
                "resource": mount.path,
                "tags": mount.tags,
                "status": mount.status,
                "item_count": len(items),
                "index_policy": policy,
                "generated_at": now_iso(),
            },
            body="\n".join(body_lines),
        )

    def _okf_item_doc(self, mount: Mount, item: dict) -> MarkdownDoc:
        title = str(item.get("title") or item.get("relative_path") or "Mounted Item")
        relative_path = str(item.get("relative_path") or "")
        source_path = str(item.get("path") or "")
        text = str(item.get("text") or "")
        body = "\n".join(
            [
                f"# {title}",
                "",
                "## Source",
                "",
                f"- Mount: `{mount.id}`",
                f"- Relative path: `{relative_path}`",
                f"- Source path: `{source_path}`",
                "",
                "## Content",
                "",
                text,
            ]
        )
        return MarkdownDoc(
            frontmatter={
                "type": "Mounted Item",
                "schema": MOUNT_ITEM_SCHEMA,
                "title": title,
                "mount_id": mount.id,
                "mount_name": mount.name,
                "mount_type": mount.type,
                "resource": source_path,
                "relative_path": relative_path,
                "tags": list(item.get("tags") or []),
                "status": str(item.get("status") or "active"),
                "indexed_at": str(item.get("indexed_at") or ""),
                "file_size": item.get("file_size"),
                "file_mtime_ns": item.get("file_mtime_ns"),
            },
            body=body,
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
            index_policy=self._index_policy(item.get("index_policy")),
        )

    def _mount_record(self, mount: Mount) -> dict:
        record = asdict(mount)
        record["index_policy"] = mount.index_policy.as_config()
        return record

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

    def _index_policy(self, value: object) -> MountIndexPolicy:
        if not isinstance(value, dict):
            return MountIndexPolicy()
        return MountIndexPolicy(
            profile=str(value.get("profile") or "raw"),
            include=[str(item) for item in self._list(value.get("include"))],
            exclude=[str(item) for item in self._list(value.get("exclude"))],
            max_file_size_kb=int(value.get("max_file_size_kb") or MAX_INDEXED_TEXT_BYTES // 1024),
        )

    def _merged_policy(
        self, current: MountIndexPolicy, update: MountIndexPolicy
    ) -> MountIndexPolicy:
        profile = normalize_slug(update.profile) if update.profile else current.profile
        if update.profile:
            include = update.include
            exclude = update.exclude
        else:
            include = _dedupe_patterns([*current.include, *update.include])
            exclude = _dedupe_patterns([*current.exclude, *update.exclude])
        max_file_size_kb = (
            update.max_file_size_kb if update.max_file_size_kb > 0 else current.max_file_size_kb
        )
        return MountIndexPolicy(
            profile=profile,
            include=include,
            exclude=exclude,
            max_file_size_kb=max_file_size_kb,
        )


def _dedupe_patterns(patterns: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for pattern in patterns:
        normalized = pattern.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _matches_any(relative_path: str, patterns: list[str]) -> bool:
    return any(_matches_pattern(relative_path, pattern) for pattern in patterns)


def _matches_pattern(relative_path: str, pattern: str) -> bool:
    if fnmatch(relative_path, pattern):
        return True
    if "/**/" in pattern and fnmatch(relative_path, pattern.replace("/**/", "/")):
        return True
    if "/" not in pattern and fnmatch(Path(relative_path).name, pattern):
        return True
    if pattern.endswith("/**"):
        root = pattern.removesuffix("/**")
        return relative_path == root or relative_path.startswith(f"{root}/")
    return False
