from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, List

import yaml

from alcove.home import AlcoveHome
from alcove.markdown import normalize_slug
from alcove.paths import compact_user_path
from alcove.radars.models import (
    DEFAULT_TTL_HOURS,
    RADAR_DEFINITION_SCHEMA,
    RadarDefinition,
    RadarSchedule,
    RadarSource,
    now_iso,
)


@dataclass(frozen=True)
class _RadarRuntimeState:
    definition: RadarDefinition
    latest_run: dict[str, Any]
    latest_reports: dict[str, str]
    report_state: str
    operational_status: str

    @property
    def status_label(self) -> str:
        if self.operational_status == "current":
            return "Current"
        if self.operational_status == "configured":
            return "Configured, not run yet"
        if self.operational_status == "stale":
            return "Stale"
        return self.operational_status.replace("-", " ").title() or "Inactive"

    @property
    def report_label(self) -> str:
        if self.report_state == "current":
            return "Latest run report"
        if self.report_state == "historical":
            return "Historical migrated report"
        return "No report yet"

    @property
    def run_command(self) -> str:
        return f"alcove radar run {self.definition.id} --json"

    def status_row(self) -> dict[str, Any]:
        return {
            "id": self.definition.id,
            "name": self.definition.name,
            "status": self.definition.status,
            "operational_status": self.operational_status,
            "status_label": self.status_label,
            "schedule": self.definition.schedule.as_dict(),
            "sources": len(self.definition.sources),
            "enabled_sources": len(
                [source for source in self.definition.sources if source.enabled]
            ),
            "last_run": self.latest_run,
            "latest_reports": self.latest_reports,
            "report_state": self.report_state,
            "report_label": self.report_label,
            "run_command": self.run_command,
        }

    def dashboard_row(self) -> dict[str, Any]:
        return {
            "id": self.definition.id,
            "name": self.definition.name,
            "status": self.operational_status,
            "definition_status": self.definition.status,
            "status_label": self.status_label,
            "schedule_enabled": self.definition.schedule.enabled,
            "ttl_hours": self.definition.schedule.ttl_hours,
            "source_count": len(self.definition.sources),
            "enabled_source_count": len(
                [source for source in self.definition.sources if source.enabled]
            ),
            "tags": list(self.definition.tags),
            "last_run": self.latest_run,
            "latest_reports": self.latest_reports,
            "report_state": self.report_state,
            "report_label": self.report_label,
            "run_command": self.run_command,
        }


class RadarModule:
    def __init__(self, home: AlcoveHome) -> None:
        self.home = home

    @property
    def root(self) -> Path:
        return self.home.root / "radars"

    @property
    def definitions_root(self) -> Path:
        return self.root / "definitions"

    @property
    def cache_root(self) -> Path:
        return self.root / "cache"

    @property
    def runs_root(self) -> Path:
        return self.root / "runs"

    @property
    def reports_root(self) -> Path:
        return self.root / "reports"

    @property
    def okf_root(self) -> Path:
        return self.root / "okf"

    @property
    def events_path(self) -> Path:
        return self.root / "events.jsonl"

    def list(self, status: str = "active") -> dict[str, Any]:
        definitions = [
            definition.as_dict()
            for definition in self._load_definitions()
            if not status or definition.status == status
        ]
        return {"count": len(definitions), "definitions": definitions}

    def get(self, radar_id: str) -> RadarDefinition:
        normalized_id = normalize_slug(radar_id)
        path = self.definitions_root / f"{normalized_id}.yml"
        if not path.is_file():
            raise FileNotFoundError(f"Radar definition not found: {radar_id}")
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise ValueError(f"Radar definition must be a mapping: {compact_user_path(path)}")
        return self._definition(payload)

    def upsert_definition(self, definition: RadarDefinition) -> dict[str, Any]:
        normalized_id = normalize_slug(definition.id)
        timestamp = now_iso()
        existing_created_at = ""
        path = self.definitions_root / f"{normalized_id}.yml"
        if path.is_file():
            existing_created_at = self.get(normalized_id).created_at
        saved = replace(
            definition,
            id=normalized_id,
            created_at=existing_created_at or definition.created_at or timestamp,
            updated_at=timestamp,
            schema=RADAR_DEFINITION_SCHEMA,
        )
        self._validate(saved)
        self.definitions_root.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(saved.as_dict(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return {
            "status": "saved",
            "path": compact_user_path(path),
            "definition": saved.as_dict(),
        }

    def preset_list(self) -> dict[str, Any]:
        presets = []
        for path in sorted(self._presets_root().glob("*.yml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict):
                presets.append(
                    {
                        "id": str(data.get("id") or path.stem),
                        "name": str(data.get("name") or path.stem),
                        "path": path.name,
                    }
                )
        return {"count": len(presets), "presets": presets}

    def init_from_preset(
        self, preset_id: str, radar_id: str = "", *, force: bool = False
    ) -> dict[str, Any]:
        preset_path = self._presets_root() / f"{normalize_slug(preset_id)}.yml"
        if not preset_path.is_file():
            raise FileNotFoundError(f"Radar preset not found: {preset_id}")
        data = yaml.safe_load(preset_path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Radar preset is invalid: {preset_id}")
        target_id = normalize_slug(radar_id or str(data.get("id") or preset_path.stem))
        if not force and (self.definitions_root / f"{target_id}.yml").is_file():
            raise FileExistsError(
                f"Radar definition already exists: {target_id}. Use --force to overwrite."
            )
        data["id"] = target_id
        return self.upsert_definition(self._definition(data))

    def run(
        self,
        radar_id: str,
        *,
        skip_fetch: bool = False,
        force: bool = False,
        ai: bool = False,
        notify: bool = False,
    ) -> dict[str, Any]:
        from alcove.radars.pipeline import RadarPipeline

        return RadarPipeline(self).run(
            self.get(radar_id),
            skip_fetch=skip_fetch,
            force=force,
            ai=ai,
            notify=notify,
        )

    def status(self, radar_id: str = "") -> dict[str, Any]:
        definitions = [self.get(radar_id)] if radar_id else self._load_definitions()
        rows = [self._status_row(definition) for definition in definitions]
        return {"count": len(rows), "radars": rows}

    def import_social_radar(
        self, source_home: str | Path = "~/.social_radar", *, force: bool = False
    ) -> dict[str, Any]:
        from alcove.radars.migration import import_social_radar

        return import_social_radar(self, source_home, force=force)

    def check_stale(self) -> dict[str, Any]:
        ran = 0
        skipped = 0
        errors = 0
        rows: List[dict[str, Any]] = []
        for definition in self._load_definitions():
            if definition.status != "active" or not definition.schedule.enabled:
                skipped += 1
                continue
            try:
                report = self.run(definition.id)
            except Exception as exc:
                errors += 1
                rows.append({"id": definition.id, "status": "error", "error": str(exc)})
                continue
            ran += 1
            rows.append(
                {
                    "id": definition.id,
                    "status": "ran",
                    "included": int(report.get("included") or 0),
                }
            )
        return {
            "status": "checked",
            "ran": ran,
            "skipped": skipped,
            "errors": errors,
            "radars": rows,
        }

    def dashboard_rows(self) -> List[dict[str, Any]]:
        return [self._dashboard_row(definition) for definition in self._load_definitions()]

    def _presets_root(self) -> Path:
        return Path(__file__).resolve().parent / "presets"

    def _load_definitions(self) -> List[RadarDefinition]:
        if not self.definitions_root.is_dir():
            return []
        definitions = []
        for path in sorted(self.definitions_root.glob("*.yml")):
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(payload, dict):
                definitions.append(self._definition(payload))
        return definitions

    def _definition(self, payload: dict[str, Any]) -> RadarDefinition:
        sources_payload = self._list_field(payload, "sources", "sources must be a list")
        sources = []
        for source in sources_payload:
            if not isinstance(source, dict):
                raise ValueError("radar source must be a mapping")
            params = self._mapping_field(source, "params", "source params must be a mapping")
            sources.append(
                RadarSource(
                    id=str(source.get("id") or ""),
                    adapter=str(source.get("adapter") or ""),
                    enabled=bool(source.get("enabled", True)),
                    limit=int(source.get("limit") or 30),
                    params=params,
                )
            )
        schedule_payload = self._mapping_field(payload, "schedule", "schedule must be a mapping")
        definition = RadarDefinition(
            id=str(payload.get("id") or ""),
            name=str(payload.get("name") or ""),
            sources=sources,
            profile=self._mapping_field(payload, "profile", "profile must be a mapping"),
            scoring=self._mapping_field(payload, "scoring", "scoring must be a mapping"),
            report=self._mapping_field(payload, "report", "report must be a mapping"),
            ai_summary=self._mapping_field(payload, "ai_summary", "ai_summary must be a mapping"),
            schedule=RadarSchedule(
                enabled=bool(schedule_payload.get("enabled", False)),
                ttl_hours=int(schedule_payload.get("ttl_hours") or DEFAULT_TTL_HOURS),
            ),
            notify=self._mapping_field(payload, "notify", "notify must be a mapping"),
            tags=[str(tag) for tag in self._list_field(payload, "tags", "tags must be a list")],
            status=str(payload.get("status") or "active"),
            created_at=str(payload.get("created_at") or ""),
            updated_at=str(payload.get("updated_at") or ""),
            schema=str(payload.get("schema") or RADAR_DEFINITION_SCHEMA),
        )
        self._validate(definition)
        return definition

    def _mapping_field(
        self, payload: dict[str, Any], field_name: str, message: str
    ) -> dict[str, Any]:
        if field_name not in payload:
            return {}
        value = payload[field_name]
        if not isinstance(value, dict):
            raise ValueError(message)
        return dict(value)

    def _list_field(self, payload: dict[str, Any], field_name: str, message: str) -> List[Any]:
        if field_name not in payload:
            return []
        value = payload[field_name]
        if not isinstance(value, list):
            raise ValueError(message)
        return list(value)

    def _validate(self, definition: RadarDefinition) -> None:
        if not definition.id or definition.id != normalize_slug(definition.id):
            raise ValueError("radar id must be normalized")
        for source in definition.sources:
            if not source.id:
                raise ValueError("source id is required")
            if not source.adapter:
                raise ValueError("source adapter is required")
        notify_sinks = definition.notify.get("sinks")
        if isinstance(notify_sinks, list) and notify_sinks:
            for sink in notify_sinks:
                if not isinstance(sink, dict):
                    raise ValueError("notify sinks must be mappings")
                sink_type = str(sink.get("type") or "telegram")
                if sink_type not in {"telegram", "feishu", "tcb", "tmux_claude_bot"}:
                    raise ValueError(f"unsupported notify sink: {sink_type}")
        else:
            channel = str(definition.notify.get("channel") or "telegram")
            if channel not in {"telegram", "feishu", "tcb", "tmux_claude_bot"}:
                raise ValueError(f"unsupported notify channel: {channel}")
        provider = str(definition.ai_summary.get("provider") or "claude")
        if provider not in {"claude", "codex"}:
            raise ValueError(f"unsupported AI summary provider: {provider}")

    def _status_row(self, definition: RadarDefinition) -> dict[str, Any]:
        return self._runtime_state(definition).status_row()

    def _runtime_state(self, definition: RadarDefinition) -> _RadarRuntimeState:
        latest_run = self._latest_run(definition.id)
        latest_reports = self._latest_reports(definition.id)
        report_state = self._latest_report_state(latest_run, latest_reports)
        return _RadarRuntimeState(
            definition=definition,
            latest_run=latest_run,
            latest_reports=latest_reports,
            report_state=report_state,
            operational_status=self._operational_status(definition, latest_run, report_state),
        )

    def _latest_run(self, radar_id: str) -> dict[str, Any]:
        run_root = self.runs_root / radar_id
        if not run_root.is_dir():
            return {}
        for run_dir in sorted(run_root.iterdir(), reverse=True):
            run_path = run_dir / "run.json"
            if not run_path.is_file():
                continue
            try:
                payload = json.loads(run_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                return dict(payload)
        return {}

    def _latest_reports(self, radar_id: str) -> dict[str, str]:
        report_root = self.reports_root / radar_id
        if not report_root.is_dir():
            return {}
        reports: dict[str, str] = {}
        for suffix in ("md", "html"):
            paths = sorted(report_root.glob(f"*.{suffix}"), reverse=True)
            if paths:
                reports[suffix] = compact_user_path(paths[0])
        return reports

    def _latest_report_state(
        self,
        latest_run: dict[str, Any],
        latest_reports: dict[str, str],
    ) -> str:
        if not latest_reports:
            return "none"
        run_reports = latest_run.get("reports") if isinstance(latest_run, dict) else {}
        if isinstance(run_reports, dict) and any(
            str(run_reports.get(suffix) or "") for suffix in latest_reports
        ):
            return "current"
        return "historical"

    def _operational_status(
        self,
        definition: RadarDefinition,
        latest_run: dict[str, Any],
        report_state: str,
    ) -> str:
        if definition.status != "active":
            return definition.status or "inactive"
        if report_state == "current":
            return "current"
        if latest_run:
            return "stale"
        return "configured"

    def _dashboard_row(self, definition: RadarDefinition) -> dict[str, Any]:
        return self._runtime_state(definition).dashboard_row()
