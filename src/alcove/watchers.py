from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
import hashlib
import json
import re
from typing import Any
from urllib.request import Request, urlopen

import yaml

from alcove.home import AlcoveHome
from alcove.inbox import InboxModule
from alcove.markdown import normalize_slug
from alcove.paths import compact_user_path
from alcove.workspace import Workspace


DEFAULT_TTL_HOURS = 24


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class WatcherSource:
    id: str
    title: str
    url: str
    kind: str = "page"
    kb: str = ""
    tags: list[str] = field(default_factory=list)
    ttl_hours: int = DEFAULT_TTL_HOURS
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""
    checked_at: str = ""
    changed_at: str = ""
    last_signature: str = ""
    last_title: str = ""
    last_error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class WatcherModule:
    def __init__(self, home: AlcoveHome) -> None:
        self.home = home
        self.root = home.root / "watchers"
        self.sources_root = self.root / "sources"
        self.events_path = self.root / "events.jsonl"

    def add(
        self,
        *,
        title: str,
        url: str,
        kind: str = "page",
        kb: str = "",
        tags: list[str] | None = None,
        ttl_hours: int = DEFAULT_TTL_HOURS,
    ) -> dict[str, Any]:
        if kb:
            self.home.get_knowledge_base(kb)
        timestamp = now_iso()
        source_id = self._unique_id(title or url)
        source = WatcherSource(
            id=source_id,
            title=title.strip() or url,
            url=url.strip(),
            kind=self._normalize_kind(kind),
            kb=kb,
            tags=[tag.strip() for tag in tags or [] if tag.strip()],
            ttl_hours=max(ttl_hours, 1),
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._write_source(source)
        return {"status": "added", "source": source.as_dict()}

    def list_sources(self, *, status: str = "active") -> dict[str, Any]:
        sources = [
            source.as_dict()
            for source in self._load_sources()
            if not status or source.status == status
        ]
        return {"count": len(sources), "sources": sources}

    def check(
        self,
        *,
        source_id: str = "",
        stale_only: bool = False,
        now: str | None = None,
    ) -> dict[str, Any]:
        timestamp = now or now_iso()
        checked = []
        changed = 0
        errors = 0
        for source in self._load_sources():
            if source.status != "active":
                continue
            if source_id and source.id != source_id:
                continue
            if stale_only and not self._is_stale(source, timestamp):
                checked.append({"id": source.id, "status": "skipped"})
                continue
            result = self._check_one(source, timestamp)
            checked.append(result)
            if result.get("status") == "changed":
                changed += 1
            if result.get("status") == "error":
                errors += 1
        return {
            "status": "checked",
            "checked": len(checked),
            "changed": changed,
            "errors": errors,
            "sources": checked,
        }

    def _check_one(self, source: WatcherSource, timestamp: str) -> dict[str, Any]:
        try:
            fetched = self._fetch(source.url)
        except Exception as exc:  # pragma: no cover - exercised through CLI in real use
            updated = self._replace_source(
                source,
                checked_at=timestamp,
                updated_at=timestamp,
                last_error=str(exc),
            )
            self._write_source(updated)
            return {"id": source.id, "status": "error", "error": str(exc)}
        title = self._extract_title(fetched["text"]) or source.title
        signature = self._signature(fetched["text"])
        status = (
            "changed" if source.last_signature and source.last_signature != signature else "fresh"
        )
        if not source.last_signature:
            status = "initialized"
        updated = self._replace_source(
            source,
            checked_at=timestamp,
            updated_at=timestamp,
            changed_at=timestamp if status == "changed" else source.changed_at,
            last_signature=signature,
            last_title=title,
            last_error="",
        )
        self._write_source(updated)
        if status == "changed":
            self._record_event(updated, title=title, timestamp=timestamp)
            self._maybe_add_to_inbox(updated, title=title, text=fetched["text"])
        return {"id": source.id, "status": status, "title": title, "url": source.url}

    def _maybe_add_to_inbox(self, source: WatcherSource, *, title: str, text: str) -> None:
        if not source.kb:
            return
        record = self.home.get_knowledge_base(source.kb)
        workspace = Workspace.discover(record.path)
        content = (
            f"Watcher detected an update for {source.title}.\n\n"
            f"URL: {source.url}\n\n"
            f"Latest title: {title}\n\n"
            f"Content preview:\n{text[:4000]}"
        )
        InboxModule(workspace).add_manual(
            title=f"Watcher update: {source.title}",
            content=content,
            source=source.url,
        )

    def _record_event(self, source: WatcherSource, *, title: str, timestamp: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        event = {
            "type": "watcher.changed",
            "timestamp": timestamp,
            "source_id": source.id,
            "title": source.title,
            "latest_title": title,
            "url": source.url,
            "kb": source.kb,
        }
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _fetch(self, url: str) -> dict[str, str]:
        if not (
            url.startswith("http://") or url.startswith("https://") or url.startswith("file://")
        ):
            raise ValueError(f"Unsupported watcher URL scheme: {url}")
        request = Request(url, headers={"User-Agent": "AlcoveWatcher/0.1"})  # noqa: S310
        with urlopen(request, timeout=20) as response:  # noqa: S310
            raw = response.read(2_000_000)
        return {"text": raw.decode("utf-8", errors="replace")}

    def _load_sources(self) -> list[WatcherSource]:
        if not self.sources_root.is_dir():
            return []
        sources = []
        for path in sorted(self.sources_root.glob("*.yml")):
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(payload, dict):
                sources.append(self._source(payload))
        return sources

    def _write_source(self, source: WatcherSource) -> None:
        self.sources_root.mkdir(parents=True, exist_ok=True)
        path = self.sources_root / f"{source.id}.yml"
        path.write_text(
            yaml.safe_dump(source.as_dict(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def _source(self, payload: dict[str, Any]) -> WatcherSource:
        return WatcherSource(
            id=str(payload.get("id") or ""),
            title=str(payload.get("title") or ""),
            url=str(payload.get("url") or ""),
            kind=str(payload.get("kind") or "page"),
            kb=str(payload.get("kb") or ""),
            tags=[str(tag) for tag in payload.get("tags") or []],
            ttl_hours=int(payload.get("ttl_hours") or DEFAULT_TTL_HOURS),
            status=str(payload.get("status") or "active"),
            created_at=str(payload.get("created_at") or ""),
            updated_at=str(payload.get("updated_at") or ""),
            checked_at=str(payload.get("checked_at") or ""),
            changed_at=str(payload.get("changed_at") or ""),
            last_signature=str(payload.get("last_signature") or ""),
            last_title=str(payload.get("last_title") or ""),
            last_error=str(payload.get("last_error") or ""),
        )

    def _unique_id(self, title: str) -> str:
        base = normalize_slug(title) or "watcher"
        existing = {source.id for source in self._load_sources()}
        if base not in existing:
            return base
        index = 2
        while f"{base}-{index}" in existing:
            index += 1
        return f"{base}-{index}"

    def _normalize_kind(self, kind: str) -> str:
        normalized = normalize_slug(kind or "page")
        if normalized not in {"page", "rss", "atom"}:
            raise ValueError(f"Unsupported watcher kind: {kind}")
        return normalized

    def _is_stale(self, source: WatcherSource, timestamp: str) -> bool:
        if not source.checked_at:
            return True
        checked_at = datetime.fromisoformat(source.checked_at)
        current = datetime.fromisoformat(timestamp)
        return current >= checked_at + timedelta(hours=max(source.ttl_hours, 1))

    def _replace_source(self, source: WatcherSource, **changes: str) -> WatcherSource:
        payload = source.as_dict()
        payload.update(changes)
        return self._source(payload)

    def _signature(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _extract_title(self, text: str) -> str:
        match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return ""
        return re.sub(r"\s+", " ", match.group(1)).strip()

    def storage_summary(self) -> dict[str, str]:
        return {
            "root": compact_user_path(self.root),
            "sources": compact_user_path(self.sources_root),
            "events": compact_user_path(self.events_path),
        }
