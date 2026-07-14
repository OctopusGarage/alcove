from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


RADAR_DEFINITION_SCHEMA = "alcove/radar-definition/v1"
RADAR_RUN_SCHEMA = "alcove/radar-run/v1"
DEFAULT_TTL_HOURS = 24


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class RadarSchedule:
    enabled: bool = False
    ttl_hours: int = DEFAULT_TTL_HOURS
    daily_time: str = ""
    timezone: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"enabled": self.enabled, "ttl_hours": max(self.ttl_hours, 1)}
        if self.daily_time:
            payload["daily_time"] = self.daily_time
        if self.timezone:
            payload["timezone"] = self.timezone
        return payload


@dataclass(frozen=True)
class RadarSource:
    id: str
    adapter: str
    enabled: bool = True
    limit: int = 30
    params: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "adapter": self.adapter,
            "enabled": self.enabled,
            "limit": self.limit,
            "params": deepcopy(self.params),
        }


@dataclass(frozen=True)
class RadarDefinition:
    id: str
    name: str
    sources: list[RadarSource] = field(default_factory=list)
    schema: str = RADAR_DEFINITION_SCHEMA
    status: str = "active"
    schedule: RadarSchedule = field(default_factory=RadarSchedule)
    profile: dict[str, Any] = field(default_factory=dict)
    scoring: dict[str, Any] = field(default_factory=dict)
    report: dict[str, Any] = field(default_factory=dict)
    ai_summary: dict[str, Any] = field(default_factory=dict)
    notify: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "id": self.id,
            "name": self.name,
            "sources": [source.as_dict().copy() for source in self.sources],
            "profile": deepcopy(self.profile),
            "scoring": deepcopy(self.scoring),
            "report": deepcopy(self.report),
            "ai_summary": deepcopy(self.ai_summary),
            "schedule": self.schedule.as_dict(),
            "notify": deepcopy(self.notify),
            "tags": list(self.tags),
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class RadarItem:
    source_id: str
    adapter: str
    title: str
    url: str = ""
    summary: str = ""
    author: str = ""
    published_at: str = ""
    tags: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    score_reason: str = ""
    included: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
