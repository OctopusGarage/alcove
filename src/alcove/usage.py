from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any
from uuid import uuid4

from alcove.home import AlcoveHome


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class UsageRecorder:
    """Record local-only usage events for dashboard aggregation."""

    def __init__(self, home: AlcoveHome) -> None:
        self.home = home

    def record_search(
        self,
        *,
        surface: str,
        query: str,
        result_count: int,
        filters: dict[str, Any] | None = None,
        duration_ms: int | None = None,
    ) -> dict[str, Any]:
        normalized_query = query.strip()
        query_preview = self._query_preview(normalized_query)
        metrics: dict[str, Any] = {
            "query_length": len(normalized_query),
            "query_hash": self._query_hash(normalized_query),
            "result_count": max(result_count, 0),
        }
        if query_preview:
            metrics["query_preview"] = query_preview
        if duration_ms is not None:
            metrics["duration_ms"] = max(duration_ms, 0)
        metadata = {"filters": self._clean_filters(filters or {})}
        return self.record_usage(
            surface=surface,
            area="search",
            action="search.run",
            summary=f"Search: {query_preview}" if query_preview else "Search used",
            outcome="empty" if result_count == 0 else "success",
            metrics=metrics,
            metadata=metadata,
            privacy={
                "query_stored": False,
                "query_preview_stored": bool(query_preview),
                "content_stored": False,
            },
        )

    def record_usage(
        self,
        *,
        surface: str,
        area: str,
        action: str,
        summary: str,
        outcome: str = "success",
        metrics: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        privacy: dict[str, bool] | None = None,
    ) -> dict[str, Any]:
        event = {
            "version": 1,
            "event_id": uuid4().hex,
            "timestamp": now_iso(),
            "surface": surface or "unknown",
            "actor": "user",
            "area": area or "usage",
            "action": action or "usage.event",
            "summary": summary or action or "Usage event",
            "outcome": outcome or "success",
            "metrics": metrics or {},
            "metadata": metadata or {},
            "privacy": privacy or {"query_stored": False, "content_stored": False},
            "visible": False,
        }
        self._append(self._usage_path(), event)
        self.write_rollups()
        return event

    def record_action(
        self,
        *,
        surface: str,
        area: str,
        action: str,
        summary: str,
        outcome: str = "success",
        metrics: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        visible: bool = True,
    ) -> dict[str, Any]:
        event = self.record_usage(
            surface=surface,
            area=area,
            action=action,
            summary=summary,
            outcome=outcome,
            metrics=metrics,
            metadata=metadata,
            privacy={"query_stored": False, "content_stored": False},
        )
        if visible:
            self.record_activity(
                area=area,
                action=action,
                summary=summary,
                metadata=metadata,
                visible=True,
            )
        return event

    def record_activity(
        self,
        *,
        area: str,
        action: str,
        summary: str,
        metadata: dict[str, Any] | None = None,
        visible: bool = True,
    ) -> dict[str, Any]:
        timestamp = now_iso()
        event = {
            "type": "event",
            "area": area or "activity",
            "action": action or "activity.event",
            "summary": summary or action or "Activity event",
            "metadata": metadata or {},
            "visible": visible,
            "timestamp": timestamp,
            "updated_at": timestamp,
        }
        self._append(self._activity_path(), event)
        return event

    def summary(self, *, limit: int = 50) -> dict[str, Any]:
        events = self._read_events(self._usage_path())
        return self._summary_from_events(events, limit=limit)

    def write_rollups(self) -> dict[str, Any]:
        events = self._read_events(self._usage_path())
        summary = self._summary_from_events(events, limit=50)
        stats_root = self.home.paths().stats
        daily_root = stats_root / "daily"
        stats_root.mkdir(parents=True, exist_ok=True)
        daily_root.mkdir(parents=True, exist_ok=True)
        (stats_root / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        for day, day_events in self._events_by_day(events).items():
            payload = self._summary_from_events(day_events, limit=20)
            payload = {
                "date": day,
                "event_count": len(day_events),
                **payload,
            }
            (daily_root / f"{day}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        return summary

    def prune(self, *, retention_days: int, now: str | None = None) -> dict[str, int]:
        cutoff = self._parse_timestamp(now or now_iso()) - timedelta(days=max(retention_days, 0))
        usage_removed = self._prune_file(self._usage_path(), "timestamp", cutoff)
        activity_removed = self._prune_file(self._activity_path(), "updated_at", cutoff)
        self.write_rollups()
        return {"usage_removed": usage_removed, "activity_removed": activity_removed}

    def _summary_from_events(self, events: list[dict[str, Any]], *, limit: int) -> dict[str, Any]:
        recent = events[-max(limit, 0) :] if limit else []
        search_events = [event for event in events if event.get("area") == "search"]
        dashboard_events = [event for event in events if event.get("area") == "dashboard"]
        action_events = [
            event for event in events if event.get("area") not in {"dashboard", "search"}
        ]
        search_surfaces = Counter(str(event.get("surface") or "unknown") for event in search_events)
        action_areas = Counter(str(event.get("area") or "unknown") for event in action_events)
        action_names = Counter(str(event.get("action") or "unknown") for event in action_events)
        search_types: Counter[str] = Counter()
        zero_result = 0
        for event in search_events:
            metrics = event.get("metrics") if isinstance(event.get("metrics"), dict) else {}
            metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
            filters = metadata.get("filters") if isinstance(metadata.get("filters"), dict) else {}
            type_filter = str(filters.get("type") or filters.get("type_filter") or "").strip()
            if type_filter:
                search_types[type_filter] += 1
            if int(metrics.get("result_count") or 0) == 0:
                zero_result += 1
        route_counter = Counter()
        for event in dashboard_events:
            metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
            route = str(metadata.get("route") or "").strip()
            if route:
                route_counter[route] += 1
        return {
            "total_events": len(events),
            "search": {
                "total": len(search_events),
                "zero_result": zero_result,
                "zero_result_rate": zero_result / len(search_events) if search_events else 0,
                "surfaces": dict(sorted(search_surfaces.items())),
                "types": dict(sorted(search_types.items())),
            },
            "dashboard": {
                "routes": dict(sorted(route_counter.items())),
            },
            "actions": {
                "total": len(action_events),
                "areas": dict(sorted(action_areas.items())),
                "names": dict(sorted(action_names.items())),
            },
            "recent": [
                {
                    "timestamp": str(event.get("timestamp") or ""),
                    "surface": str(event.get("surface") or ""),
                    "area": str(event.get("area") or ""),
                    "action": str(event.get("action") or ""),
                    "outcome": str(event.get("outcome") or ""),
                    "summary": str(event.get("summary") or ""),
                    "metrics": event.get("metrics")
                    if isinstance(event.get("metrics"), dict)
                    else {},
                }
                for event in reversed(recent)
            ],
        }

    def _events_by_day(self, events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for event in events:
            timestamp = str(event.get("timestamp") or "")
            if not timestamp:
                continue
            day = timestamp[:10]
            if len(day) == 10:
                grouped.setdefault(day, []).append(event)
        return grouped

    def _prune_file(self, path: Any, timestamp_key: str, cutoff: datetime) -> int:
        events = self._read_events(path)
        if not events:
            return 0
        kept: list[dict[str, Any]] = []
        removed = 0
        for event in events:
            timestamp = str(event.get(timestamp_key) or event.get("timestamp") or "")
            if timestamp and self._parse_timestamp(timestamp) < cutoff:
                removed += 1
                continue
            kept.append(event)
        path.write_text(
            "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in kept),
            encoding="utf-8",
        )
        return removed

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _query_hash(self, query: str) -> str:
        if not query:
            return ""
        salt_path = self.home.paths().logs / ".usage_salt"
        salt_path.parent.mkdir(parents=True, exist_ok=True)
        if not salt_path.exists():
            salt_path.write_text(uuid4().hex, encoding="utf-8")
        salt = salt_path.read_text(encoding="utf-8").strip()
        return hashlib.sha256(f"{salt}:{query.casefold()}".encode("utf-8")).hexdigest()

    @staticmethod
    def _query_preview(query: str, max_chars: int = 32) -> str:
        normalized = " ".join(query.split())
        if not normalized:
            return ""
        if len(normalized) <= 4:
            return normalized
        if len(normalized) <= max_chars:
            return f"{normalized[:8].rstrip()}...{normalized[-4:].lstrip()}"
        return f"{normalized[:max_chars].rstrip()}..."

    @staticmethod
    def _clean_filters(filters: dict[str, Any]) -> dict[str, str]:
        clean: dict[str, str] = {}
        for key, value in filters.items():
            if value in {None, ""}:
                continue
            clean[str(key)] = str(value)
        return clean

    def _usage_path(self) -> Any:
        return self.home.paths().logs / "usage.jsonl"

    def _activity_path(self) -> Any:
        return self.home.paths().logs / "activity.jsonl"

    @staticmethod
    def _append(path: Any, event: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    @staticmethod
    def _read_events(path: Any) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                rows.append(event)
        return rows
