from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
import hashlib
import json
import platform
import re
from pathlib import Path
from typing import Any

from alcove.connector_sources import ConnectorSourceRegistry, DEFAULT_TTL_HOURS
from alcove.external_index import ExternalIndexItemFactory, ExternalIndexStore
from alcove.home import AlcoveHome
from alcove.paths import compact_user_path
from alcove.runtime import AlcoveRuntime
from alcove.taxonomy import load_taxonomy, normalize_tag
from alcove.workspace import Workspace

from .okf_index import write_connector_okf_index, write_connector_okf_sources


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class ChromeBookmarksImportRequest:
    export_file: str
    tags: list[str] = field(default_factory=list)
    source_id: str = ""


@dataclass(frozen=True)
class ChromeBookmarksLocalImportRequest:
    source_file: str = ""
    profile: str = "Default"
    source_id: str = "default"
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BookmarkRecord:
    title: str
    url: str
    folder_path: str = ""
    date_added: str = ""
    date_modified: str = ""

    @property
    def signature(self) -> str:
        return json.dumps(
            {
                "title": self.title,
                "url": self.url,
                "folder_path": self.folder_path,
                "date_added": self.date_added,
                "date_modified": self.date_modified,
            },
            ensure_ascii=False,
            sort_keys=True,
        )


class ChromeBookmarksConnector:
    connector_id = "chrome-bookmarks"
    connector_name = "Chrome Bookmarks"
    item_type = "Chrome Bookmark"

    def __init__(self, workspace: Workspace | None = None, home: AlcoveHome | None = None) -> None:
        self.runtime = AlcoveRuntime.from_modules(workspace=workspace, home=home)
        self.workspace = self.runtime.workspace
        self.home = self.runtime.home
        self.taxonomy = load_taxonomy(self.runtime.taxonomy_root)
        self.connector_dir = self.runtime.connectors_root / self.connector_id
        self.index_path = self.connector_dir / "index.json"
        self.index_store = ExternalIndexStore(self.runtime.connectors_root)

    def import_export(self, request: ChromeBookmarksImportRequest) -> dict[str, Any]:
        export_file = Path(request.export_file).expanduser().resolve()
        if not export_file.is_file():
            raise FileNotFoundError(f"Chrome bookmarks file not found: {export_file}")
        records = self._read_bookmarks(export_file)
        tags = self._normalize_tags(request.tags)
        items = self._items(records, export_file, tags, source_id=request.source_id)
        self._save_index(items, export_file, source_id=request.source_id)
        return {
            "connector": self.connector_id,
            "export_file": compact_user_path(export_file),
            "index_path": compact_user_path(self.index_path),
            "scanned": len(items),
            "skipped": 0,
            "items": items,
        }

    def import_local(self, request: ChromeBookmarksLocalImportRequest) -> dict[str, Any]:
        source_file = self._source_file(request)
        old_records = self._read_index_records(source_id=request.source_id)
        report = self.import_export(
            ChromeBookmarksImportRequest(
                export_file=str(source_file),
                tags=request.tags,
                source_id=request.source_id,
            )
        )
        new_records = self._read_bookmarks(source_file)
        diff = self._diff_records(old_records, new_records)
        ConnectorSourceRegistry(self.workspace, home=self.home).upsert_chrome_bookmarks(
            source_id=request.source_id,
            source=f"Chrome Bookmarks: {request.profile}",
            profile=request.profile,
            tags=self._normalize_tags(request.tags),
            source_file=source_file,
            index_path=self.index_path,
            item_count=len(new_records),
        )
        self._write_okf_sources_from_registry()
        return {
            **report,
            "source": f"Chrome Bookmarks: {request.profile}",
            "profile": request.profile,
            "source_id": request.source_id,
            "source_file": compact_user_path(source_file),
            "exported": len(new_records),
            "diff": diff,
        }

    def refresh_sources(
        self,
        *,
        stale_only: bool = False,
        source_id: str = "",
        now: str | None = None,
        default_ttl_hours: int = DEFAULT_TTL_HOURS,
    ) -> dict[str, Any]:
        registry = ConnectorSourceRegistry(self.workspace, home=self.home)
        sources = registry.list(self.connector_id)
        if source_id:
            sources = [source for source in sources if str(source.get("id") or "") == source_id]
        if stale_only:
            stale_ids = {
                str(source.get("id") or "")
                for source in registry.stale_sources(
                    connector=self.connector_id,
                    now=now,
                    default_ttl_hours=default_ttl_hours,
                )
            }
            sources = [source for source in sources if str(source.get("id") or "") in stale_ids]

        reports = []
        for source in sources:
            try:
                report = self._refresh_source(source)
            except Exception as exc:
                report = self._refresh_error(source, exc)
            reports.append(report)
        return {
            "connector": self.connector_id,
            "refreshed": sum(1 for report in reports if report["status"] == "refreshed"),
            "skipped": sum(1 for report in reports if report["status"] == "not_modified"),
            "errors": sum(1 for report in reports if report["status"] == "error"),
            "sources": reports,
        }

    def _refresh_source(self, source: dict[str, Any]) -> dict[str, Any]:
        source_id = str(source.get("id") or "default")
        source_file = Path(str(source.get("source_file") or "")).expanduser()
        if not source_file.is_absolute():
            source_file = source_file.resolve()
        tags = [str(tag) for tag in source.get("tags") or []]
        old_records = self._read_index_records(source_id=source_id)
        report = self.import_export(
            ChromeBookmarksImportRequest(
                export_file=str(source_file),
                tags=tags,
                source_id=source_id,
            )
        )
        new_records = self._read_bookmarks(source_file)
        diff = self._diff_records(old_records, new_records)
        status = (
            "not_modified"
            if not diff["added"] and not diff["removed"] and not diff["updated"]
            else "refreshed"
        )
        refresh = source.get("refresh") if isinstance(source.get("refresh"), dict) else {}
        ConnectorSourceRegistry(self.workspace, home=self.home).upsert_chrome_bookmarks(
            source_id=source_id,
            source=str(source.get("source") or "Chrome Bookmarks: Default"),
            profile=str(source.get("profile") or "Default"),
            tags=self._normalize_tags(tags),
            source_file=source_file,
            index_path=self.index_path,
            item_count=len(new_records),
            changed_at=str(refresh.get("last_changed_at") or "")
            if status == "not_modified"
            else None,
            status="fresh",
        )
        self._write_okf_sources_from_registry()
        return {
            "connector": self.connector_id,
            "id": source_id,
            "status": status,
            "exported": len(new_records),
            "scanned": report["scanned"],
            "skipped": report["skipped"],
            "source_file": compact_user_path(source_file),
            "index_path": compact_user_path(self.index_path),
            "diff": diff,
            "error": "",
        }

    def _refresh_error(self, source: dict[str, Any], exc: Exception) -> dict[str, Any]:
        source_id = str(source.get("id") or "default")
        source_file = Path(str(source.get("source_file") or "")).expanduser()
        refresh = source.get("refresh") if isinstance(source.get("refresh"), dict) else {}
        item_count = _int_value(refresh.get("item_count"), 0)
        ConnectorSourceRegistry(self.workspace, home=self.home).upsert_chrome_bookmarks(
            source_id=source_id,
            source=str(source.get("source") or "Chrome Bookmarks: Default"),
            profile=str(source.get("profile") or "Default"),
            tags=[str(tag) for tag in source.get("tags") or []],
            source_file=source_file,
            index_path=self.index_path,
            item_count=item_count,
            changed_at=str(refresh.get("last_changed_at") or ""),
            status="error",
            error=str(exc),
        )
        self._write_okf_sources_from_registry()
        return {
            "connector": self.connector_id,
            "id": source_id,
            "status": "error",
            "exported": item_count,
            "scanned": item_count,
            "skipped": 0,
            "source_file": compact_user_path(source_file),
            "index_path": compact_user_path(self.index_path),
            "diff": {"added": [], "removed": [], "updated": [], "unchanged": item_count},
            "error": str(exc),
        }

    def _read_bookmarks(self, path: Path) -> list[BookmarkRecord]:
        text = path.read_text(encoding="utf-8")
        stripped = text.lstrip()
        if stripped.startswith("<") or "<!DOCTYPE NETSCAPE-Bookmark-file-1" in text[:200]:
            return _BookmarksHtmlParser.parse(text)
        data = json.loads(text)
        return self._records_from_chrome_json(data)

    def _records_from_chrome_json(self, data: object) -> list[BookmarkRecord]:
        if not isinstance(data, dict):
            return []
        records: list[BookmarkRecord] = []
        roots = data.get("roots")
        if isinstance(roots, dict):
            for key, node in roots.items():
                if not isinstance(node, dict):
                    continue
                root_name = str(node.get("name") or _root_label(str(key)))
                self._walk_json_node(node, [root_name] if root_name else [], records)
            return records
        self._walk_json_node(data, [], records)
        return records

    def _walk_json_node(
        self,
        node: dict[str, Any],
        folders: list[str],
        records: list[BookmarkRecord],
    ) -> None:
        node_type = str(node.get("type") or "")
        if node_type == "url":
            title = str(node.get("name") or "").strip()
            url = str(node.get("url") or "").strip()
            if title and url:
                records.append(
                    BookmarkRecord(
                        title=title,
                        url=url,
                        folder_path="/".join(part for part in folders if part),
                        date_added=_chrome_time(node.get("date_added")),
                        date_modified=_chrome_time(node.get("date_modified")),
                    )
                )
            return
        children = node.get("children")
        if isinstance(children, list):
            next_folders = folders
            if node_type == "folder" and not folders:
                name = str(node.get("name") or "").strip()
                next_folders = [name] if name else []
            for child in children:
                if not isinstance(child, dict):
                    continue
                if str(child.get("type") or "") == "folder":
                    folder_name = str(child.get("name") or "").strip()
                    self._walk_json_node(
                        child,
                        [*next_folders, folder_name] if folder_name else next_folders,
                        records,
                    )
                else:
                    self._walk_json_node(child, next_folders, records)

    def _item(
        self,
        record: BookmarkRecord,
        export_file: Path,
        tags: list[str],
        *,
        source_id: str = "",
        relative_path: str = "",
    ) -> dict[str, Any]:
        text_parts = [
            record.title,
            record.url,
            record.folder_path,
            f"added: {record.date_added}" if record.date_added else "",
        ]
        return ExternalIndexItemFactory.connector_item(
            connector_id=self.connector_id,
            connector_name=self.connector_name,
            item_type=self.item_type,
            title=record.title,
            account="chrome",
            folder_path=record.folder_path,
            path=compact_user_path(export_file),
            resource=record.url,
            relative_path=relative_path or self._relative_path(source_id, record),
            text="\n".join(part for part in text_parts if part),
            tags=tags,
            status="active",
            indexed_at=now_iso(),
            extra={
                "date_added": record.date_added,
                "date_modified": record.date_modified,
                **({"source_id": source_id} if source_id else {}),
            },
        )

    def _items(
        self,
        records: list[BookmarkRecord],
        export_file: Path,
        tags: list[str],
        *,
        source_id: str = "",
    ) -> list[dict[str, Any]]:
        seen: dict[str, int] = {}
        items = []
        for record in records:
            base_path = self._relative_path(source_id, record)
            seen[base_path] = seen.get(base_path, 0) + 1
            relative_path = base_path if seen[base_path] == 1 else f"{base_path}-{seen[base_path]}"
            items.append(
                self._item(
                    record,
                    export_file,
                    tags,
                    source_id=source_id,
                    relative_path=relative_path,
                )
            )
        return items

    def _save_index(
        self, items: list[dict[str, Any]], export_file: Path, *, source_id: str = ""
    ) -> None:
        self.connector_dir.mkdir(parents=True, exist_ok=True)
        compact_export_file = compact_user_path(export_file)
        if source_id:
            items = self._merged_source_items(
                source_id=source_id,
                export_file=compact_export_file,
                items=items,
            )
        indexed_at = now_iso()
        self.index_store.write_connector_index(
            self.connector_id,
            {
                "schema_version": 1,
                "connector": self.connector_id,
                "export_file": compact_export_file,
                "indexed_at": indexed_at,
                "items": items,
            },
        )
        self._write_okf_index(items, generated_at=indexed_at)

    def _write_okf_index(self, items: list[dict[str, Any]], *, generated_at: str) -> None:
        write_connector_okf_index(
            connector_dir=self.connector_dir,
            connector_id=self.connector_id,
            connector_name=self.connector_name,
            items=items,
            generated_at=generated_at,
        )

    def _write_okf_sources_from_registry(self) -> None:
        sources = ConnectorSourceRegistry(self.workspace, home=self.home).list(self.connector_id)
        write_connector_okf_sources(
            connector_dir=self.connector_dir,
            connector_id=self.connector_id,
            connector_name=self.connector_name,
            sources=sources,
            generated_at=now_iso(),
        )

    def _read_index_records(self, *, source_id: str = "") -> list[BookmarkRecord]:
        payload = self.index_store.read_file(self.index_path)
        if payload is None or not isinstance(payload.get("items"), list):
            return []
        records = []
        for item in payload["items"]:
            if not isinstance(item, dict):
                continue
            if source_id and str(item.get("source_id") or "") != source_id:
                continue
            records.append(
                BookmarkRecord(
                    title=str(item.get("title") or ""),
                    url=str(item.get("resource") or ""),
                    folder_path=str(item.get("folder_path") or ""),
                    date_added=str(item.get("date_added") or ""),
                    date_modified=str(item.get("date_modified") or ""),
                )
            )
        return records

    def _diff_records(
        self,
        old_records: list[BookmarkRecord],
        new_records: list[BookmarkRecord],
    ) -> dict[str, Any]:
        old_by_key = self._records_by_key(old_records)
        new_by_key = self._records_by_key(new_records)
        added: list[str] = []
        removed: list[str] = []
        updated: list[str] = []
        unchanged = 0
        for key in sorted(set(old_by_key) | set(new_by_key)):
            old_group = old_by_key.get(key, [])
            new_group = new_by_key.get(key, [])
            if not old_group:
                added.extend(record.title for record in new_group)
                continue
            if not new_group:
                removed.extend(record.title for record in old_group)
                continue
            old_signatures = Counter(record.signature for record in old_group)
            new_signatures = Counter(record.signature for record in new_group)
            unchanged_for_key = sum(
                min(old_signatures[signature], new_signatures[signature])
                for signature in set(old_signatures) | set(new_signatures)
            )
            unchanged += unchanged_for_key
            paired_changed = min(len(old_group), len(new_group)) - unchanged_for_key
            if paired_changed > 0:
                changed_titles = [
                    record.title
                    for record in new_group
                    if old_signatures[record.signature] < new_signatures[record.signature]
                ]
                updated.extend(changed_titles[:paired_changed])
            if len(new_group) > len(old_group):
                added.extend(record.title for record in new_group[len(old_group) :])
            if len(old_group) > len(new_group):
                removed.extend(record.title for record in old_group[len(new_group) :])
        return {
            "added": added,
            "removed": removed,
            "updated": updated,
            "unchanged": unchanged,
        }

    def _records_by_key(self, records: list[BookmarkRecord]) -> dict[str, list[BookmarkRecord]]:
        grouped: dict[str, list[BookmarkRecord]] = defaultdict(list)
        for record in records:
            grouped[self._record_key(record)].append(record)
        return dict(grouped)

    def _merged_source_items(
        self,
        *,
        source_id: str,
        export_file: str,
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        payload = self.index_store.read_file(self.index_path)
        existing = []
        if payload is not None and isinstance(payload.get("items"), list):
            existing = [item for item in payload["items"] if isinstance(item, dict)]
        return [
            item
            for item in existing
            if not self._belongs_to_source(item, source_id=source_id, export_file=export_file)
        ] + items

    def _belongs_to_source(self, item: dict[str, Any], *, source_id: str, export_file: str) -> bool:
        item_source_id = str(item.get("source_id") or "")
        if item_source_id:
            return item_source_id == source_id
        return str(item.get("path") or "") == export_file

    def _relative_path(self, source_id: str, record: BookmarkRecord) -> str:
        slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", record.title.lower()).strip("-") or "bookmark"
        digest = hashlib.sha256(f"{record.folder_path}\0{record.url}".encode("utf-8")).hexdigest()[
            :10
        ]
        path = f"bookmarks/{slug}-{digest}"
        return f"{source_id}/{path}" if source_id else path

    def _record_key(self, record: BookmarkRecord) -> str:
        return hashlib.sha256(f"{record.folder_path}\0{record.url}".encode("utf-8")).hexdigest()

    def _normalize_tags(self, tags: list[str]) -> list[str]:
        normalized = {normalize_tag(tag, self.taxonomy) for tag in tags}
        return sorted(tag for tag in normalized if tag)

    def _source_file(self, request: ChromeBookmarksLocalImportRequest) -> Path:
        if request.source_file:
            return Path(request.source_file).expanduser().resolve()
        return _default_chrome_bookmarks_path(request.profile).resolve()


class _BookmarksHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.records: list[BookmarkRecord] = []
        self.folder_stack: list[str] = []
        self.pending_folder = ""
        self.capture_folder = False
        self.capture_link = False
        self.link_attrs: dict[str, str] = {}
        self.buffer: list[str] = []

    @classmethod
    def parse(cls, text: str) -> list[BookmarkRecord]:
        parser = cls()
        parser.feed(text)
        return parser.records

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower = tag.lower()
        if lower == "h3":
            self.capture_folder = True
            self.buffer = []
            return
        if lower == "dl" and self.pending_folder:
            self.folder_stack.append(self.pending_folder)
            self.pending_folder = ""
            return
        if lower == "a":
            self.capture_link = True
            self.link_attrs = {key.lower(): value or "" for key, value in attrs}
            self.buffer = []

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower == "h3" and self.capture_folder:
            self.pending_folder = _squash_text("".join(self.buffer))
            self.capture_folder = False
            self.buffer = []
            return
        if lower == "a" and self.capture_link:
            title = _squash_text("".join(self.buffer))
            url = self.link_attrs.get("href", "").strip()
            if title and url:
                self.records.append(
                    BookmarkRecord(
                        title=title,
                        url=url,
                        folder_path="/".join(self.folder_stack),
                        date_added=_unix_time(self.link_attrs.get("add_date")),
                    )
                )
            self.capture_link = False
            self.link_attrs = {}
            self.buffer = []
            return
        if lower == "dl" and self.folder_stack:
            self.folder_stack.pop()

    def handle_data(self, data: str) -> None:
        if self.capture_folder or self.capture_link:
            self.buffer.append(data)


def _default_chrome_bookmarks_path(profile_name: str) -> Path:
    profile_dir = profile_name.strip() or "Default"
    system = platform.system().lower()
    home = Path.home()
    if system == "darwin":
        return (
            home
            / "Library"
            / "Application Support"
            / "Google"
            / "Chrome"
            / profile_dir
            / "Bookmarks"
        )
    if system == "windows":
        return (
            home
            / "AppData"
            / "Local"
            / "Google"
            / "Chrome"
            / "User Data"
            / profile_dir
            / "Bookmarks"
        )
    chrome_path = home / ".config" / "google-chrome" / profile_dir / "Bookmarks"
    if chrome_path.exists():
        return chrome_path
    return home / ".config" / "chromium" / profile_dir / "Bookmarks"


def _root_label(root_key: str) -> str:
    return {
        "bookmark_bar": "Bookmarks Bar",
        "other": "Other Bookmarks",
        "synced": "Mobile Bookmarks",
    }.get(root_key, root_key)


def _chrome_time(value: object) -> str:
    try:
        micros = int(str(value))
    except (TypeError, ValueError):
        return ""
    if micros <= 0:
        return ""
    return (datetime(1601, 1, 1, tzinfo=UTC) + timedelta(microseconds=micros)).isoformat(
        timespec="seconds"
    )


def _unix_time(value: object) -> str:
    try:
        seconds = int(str(value))
    except (TypeError, ValueError):
        return ""
    if seconds <= 0:
        return ""
    return datetime.fromtimestamp(seconds, tz=UTC).isoformat(timespec="seconds")


def _squash_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _int_value(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
