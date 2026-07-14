from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable, Protocol

import yaml

from alcove.home import AlcoveHome
from alcove.markdown import normalize_slug
from alcove.paths import compact_user_path
from alcove.pins import PinsModule
from alcove.projects import ProjectsModule
from alcove.prompts import PromptsModule
from alcove.publisher_dirty import (
    clear_publisher_dirty_sources,
    dirty_sources_for_publisher,
)
from alcove.publisher_rendering import (
    content_hash as _content_hash,
    markdown_as_apple_notes_html as _markdown_as_html,
    render_pins_digest,
    render_planner_digest,
    render_project_registry,
    render_prompt_library,
)
from alcove.tasks import TasksModule


PUBLISHER_DEFINITION_SCHEMA = "alcove/publisher-definition/v1"
PUBLISHER_STATE_SCHEMA = "alcove/publisher-state/v1"
DEFAULT_PUBLISHER_ID = "apple-notes"


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _publisher_remediation_hint(code: str) -> str:
    hints = {
        "TARGET_AMBIGUOUS": (
            "Choose the intended note, rename or remove duplicate Apple Notes, "
            "or clear the publisher target state before rerunning."
        ),
        "TARGET_MISSING": (
            "Enable recreate_missing for this target, restore the missing note, "
            "or clear the stale note_id before rerunning."
        ),
        "AUTOMATION_PERMISSION_DENIED": (
            "Grant the terminal or agent process permission to control Notes.app "
            "in macOS Privacy & Security, then rerun the publisher."
        ),
        "APPLE_NOTES_UNAVAILABLE": (
            "Run on macOS with Notes.app and osascript available, or use the file "
            "adapter smoke mode for tests."
        ),
        "RENDER_FAILED": "Fix the source/template configuration and rerun the publisher.",
    }
    return hints.get(code, "Inspect the target error, fix the publisher target, then rerun.")


class PublishError(Exception):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class TargetRef:
    note_id: str
    folder_path: str
    title: str


class AppleNotesTarget(Protocol):
    def resolve_or_create(
        self,
        *,
        folder_path: str,
        title: str,
        note_id: str = "",
        recreate_missing: bool = False,
    ) -> TargetRef: ...

    def replace_note_body(self, *, note_id: str, title: str, body: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class PublisherSource:
    module: str
    filter: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PublisherRender:
    template: str
    title: str


@dataclass(frozen=True)
class PublisherTarget:
    folder: str
    title: str
    type: str = "apple-notes"
    mode: str = "replace"
    recreate_missing: bool | None = None


@dataclass(frozen=True)
class PublisherTargetDefinition:
    id: str
    source: PublisherSource
    render: PublisherRender
    target: PublisherTarget


@dataclass(frozen=True)
class PublisherSchedule:
    enabled: bool = True
    ttl_hours: int = 24


@dataclass(frozen=True)
class PublisherDefinition:
    id: str
    status: str = "active"
    schedule: PublisherSchedule = field(default_factory=PublisherSchedule)
    target_defaults: dict[str, Any] = field(default_factory=dict)
    targets: list[PublisherTargetDefinition] = field(default_factory=list)


@dataclass(frozen=True)
class PublisherTargetState:
    note_id: str = ""
    folder_path: str = ""
    title: str = ""
    content_hash: str = ""
    last_synced_at: str = ""
    last_status: str = ""
    last_error: str = ""


@dataclass(frozen=True)
class PublisherRenderContext:
    home: AlcoveHome
    target: PublisherTargetDefinition
    timestamp: str


PublisherRenderHandler = Callable[[PublisherRenderContext], str]


class PublisherRenderRegistry:
    """Owns publisher source/template rendering without leaking module branches."""

    def __init__(
        self,
        handlers: dict[tuple[str, str], PublisherRenderHandler] | None = None,
    ) -> None:
        self._handlers = handlers or self._default_handlers()

    def render(
        self,
        *,
        home: AlcoveHome,
        target: PublisherTargetDefinition,
        timestamp: str,
    ) -> str:
        key = (target.source.module, target.render.template)
        handler = self._handlers.get(key)
        if handler is None:
            raise PublishError(
                "RENDER_FAILED",
                f"Unsupported publisher source/template: {key[0]}/{key[1]}",
            )
        return handler(PublisherRenderContext(home=home, target=target, timestamp=timestamp))

    def _default_handlers(self) -> dict[tuple[str, str], PublisherRenderHandler]:
        return {
            ("pins", "pins_digest"): self._render_pins_digest,
            ("tasks", "planner_digest"): self._render_planner_digest,
            ("prompts", "prompt_library"): self._render_prompt_library,
            ("projects", "project_registry"): self._render_project_registry,
        }

    def _render_pins_digest(self, context: PublisherRenderContext) -> str:
        kind = str(context.target.source.filter.get("kind") or "")
        status = str(context.target.source.filter.get("status") or "active")
        pins = [
            pin
            for pin in PinsModule(home=context.home).list(status=status)
            if not kind or pin.kind == kind
        ]
        return render_pins_digest(
            title=context.target.render.title,
            pins=pins,
            timestamp=context.timestamp,
        )

    def _render_planner_digest(self, context: PublisherRenderContext) -> str:
        task_module = TasksModule(home=context.home)
        return render_planner_digest(
            title=context.target.render.title,
            tasks=task_module.task_list(status="pending"),
            ideas=task_module.idea_list(status="active"),
            routines=task_module.routine_list(status="active"),
            timestamp=context.timestamp,
        )

    def _render_prompt_library(self, context: PublisherRenderContext) -> str:
        return render_prompt_library(
            title=context.target.render.title,
            prompts=PromptsModule(home=context.home).list(status="active"),
            timestamp=context.timestamp,
        )

    def _render_project_registry(self, context: PublisherRenderContext) -> str:
        return render_project_registry(
            title=context.target.render.title,
            projects=ProjectsModule(home=context.home).list(),
            timestamp=context.timestamp,
        )


class PublisherModule:
    def __init__(
        self,
        home: AlcoveHome,
        *,
        target_factory: Callable[[PublisherDefinition], AppleNotesTarget] | None = None,
        render_registry: PublisherRenderRegistry | None = None,
    ) -> None:
        self.home = home
        self.root = home.root / "publishers"
        self.definitions_root = self.root / "definitions"
        self.state_root = self.root / "state"
        self.renders_root = self.root / "renders"
        self.runs_root = self.root / "runs"
        self.events_path = self.root / "events.jsonl"
        self.target_factory = target_factory
        self.render_registry = render_registry or PublisherRenderRegistry()

    def init_apple_notes(self, *, root_folder: str = "iCloud/Alcove") -> dict[str, Any]:
        definition_path = self.definitions_root / f"{DEFAULT_PUBLISHER_ID}.yml"
        if definition_path.exists():
            existing = self._definition_from_dict(
                yaml.safe_load(definition_path.read_text(encoding="utf-8")) or {}
            )
            default = self._default_apple_notes_definition(root_folder=root_folder)
            added = self._merge_missing_default_targets(existing, default)
            if added:
                self._write_definition(
                    PublisherDefinition(
                        id=existing.id,
                        status=existing.status,
                        schedule=existing.schedule,
                        target_defaults=existing.target_defaults,
                        targets=[*existing.targets, *added],
                    )
                )
                return {
                    "status": "updated",
                    "publisher": DEFAULT_PUBLISHER_ID,
                    "path": compact_user_path(definition_path),
                    "added_targets": [target.id for target in added],
                }
            return {
                "status": "exists",
                "publisher": DEFAULT_PUBLISHER_ID,
                "path": compact_user_path(definition_path),
            }
        definition = self._default_apple_notes_definition(root_folder=root_folder)
        self._write_definition(definition)
        return {
            "status": "initialized",
            "publisher": definition.id,
            "path": compact_user_path(definition_path),
            "targets": [target.id for target in definition.targets],
        }

    def list(self, *, status: str = "active") -> dict[str, Any]:
        definitions = [
            definition
            for definition in self._load_definitions()
            if not status or definition.status == status
        ]
        return {
            "count": len(definitions),
            "publishers": [
                {
                    "id": definition.id,
                    "status": definition.status,
                    "schedule": asdict(definition.schedule),
                    "targets": [target.id for target in definition.targets],
                }
                for definition in definitions
            ],
        }

    def run(
        self,
        publisher_id: str,
        *,
        target_id: str = "",
        force: bool = False,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        timestamp = timestamp or now_iso()
        definition = self._load_definition(publisher_id)
        state = self._load_state(definition.id)
        adapter = self._target_adapter(definition)
        results = []
        updated = 0
        skipped = 0
        errors = 0
        for target in definition.targets:
            if target_id and target.id != target_id:
                continue
            result = self._run_target(
                definition=definition,
                target=target,
                state=state,
                adapter=adapter,
                force=force,
                timestamp=timestamp,
            )
            results.append(result)
            if result["status"] == "updated":
                updated += 1
            elif result["status"] == "skipped":
                skipped += 1
            elif result["status"] == "failed":
                errors += 1
        payload = {
            "status": "success" if errors == 0 else "partial",
            "publisher": definition.id,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
            "targets": results,
        }
        self._write_run(definition.id, payload)
        self._record_event(definition.id, payload, timestamp=timestamp)
        return payload

    def run_due(self, *, timestamp: str | None = None) -> dict[str, Any]:
        timestamp = timestamp or now_iso()
        ran = 0
        skipped = 0
        updated = 0
        errors = 0
        results = []
        for definition in self._load_definitions():
            if definition.status != "active" or not definition.schedule.enabled:
                skipped += 1
                results.append(
                    {"publisher": definition.id, "status": "skipped", "reason": "inactive"}
                )
                continue
            dirty_sources = self._dirty_sources(definition)
            if not self._is_due(definition, timestamp) and not dirty_sources:
                skipped += 1
                results.append(
                    {"publisher": definition.id, "status": "skipped", "reason": "not_due"}
                )
                continue
            result = self.run(definition.id, timestamp=timestamp)
            if dirty_sources:
                result["due_reason"] = "dirty"
                result["dirty_sources"] = sorted(dirty_sources)
                if int(result.get("errors") or 0) == 0:
                    clear_publisher_dirty_sources(self.home, definition.id, dirty_sources)
            ran += 1
            updated += int(result.get("updated") or 0)
            errors += int(result.get("errors") or 0)
            results.append(result)
        return {
            "status": "checked",
            "ran": ran,
            "skipped": skipped,
            "updated": updated,
            "errors": errors,
            "publishers": results,
        }

    def _run_target(
        self,
        *,
        definition: PublisherDefinition,
        target: PublisherTargetDefinition,
        state: dict[str, PublisherTargetState],
        adapter: AppleNotesTarget,
        force: bool,
        timestamp: str,
    ) -> dict[str, Any]:
        try:
            folder_path = self._folder_path(definition, target)
            title = target.target.title or target.render.title
            body = self._render(target, timestamp=timestamp)
            content_hash = _content_hash(body)
            previous = state.get(target.id, PublisherTargetState())
            if not force and previous.content_hash == content_hash and previous.note_id:
                return {
                    "id": target.id,
                    "status": "skipped",
                    "reason": "unchanged",
                    "note_id": previous.note_id,
                    "content_hash": content_hash,
                }
            ref = adapter.resolve_or_create(
                folder_path=folder_path,
                title=title,
                note_id=previous.note_id,
                recreate_missing=self._recreate_missing(definition, target),
            )
            replace = adapter.replace_note_body(note_id=ref.note_id, title=title, body=body)
            self._write_render(target.id, body)
            state[target.id] = PublisherTargetState(
                note_id=ref.note_id,
                folder_path=ref.folder_path,
                title=title,
                content_hash=content_hash,
                last_synced_at=timestamp,
                last_status="success",
                last_error="",
            )
            self._write_state(definition.id, state)
            return {
                "id": target.id,
                "status": "updated",
                "note_id": ref.note_id,
                "folder_path": ref.folder_path,
                "title": title,
                "content_hash": content_hash,
                "target": replace,
            }
        except PublishError as exc:
            self._record_target_error(definition.id, target.id, state, exc, timestamp)
            payload = {
                "id": target.id,
                "status": "failed",
                "error_code": exc.code,
                "error": exc.message,
                "remediation_hint": _publisher_remediation_hint(exc.code),
            }
            if exc.details:
                payload["details"] = exc.details
            return payload
        except Exception as exc:  # pragma: no cover - defensive boundary for target adapters.
            error = PublishError("RENDER_FAILED", str(exc))
            self._record_target_error(definition.id, target.id, state, error, timestamp)
            return {
                "id": target.id,
                "status": "failed",
                "error_code": error.code,
                "error": error.message,
                "remediation_hint": _publisher_remediation_hint(error.code),
            }

    def _render(self, target: PublisherTargetDefinition, *, timestamp: str) -> str:
        return self.render_registry.render(
            home=self.home,
            target=target,
            timestamp=timestamp,
        )

    def _target_adapter(self, definition: PublisherDefinition) -> AppleNotesTarget:
        if self.target_factory is not None:
            return self.target_factory(definition)
        fake_root = os.environ.get("ALCOVE_FAKE_APPLE_NOTES_DIR", "")
        if fake_root:
            return FileAppleNotesTarget(Path(fake_root))
        return LocalAppleNotesTarget()

    def _load_definitions(self) -> list[PublisherDefinition]:
        if not self.definitions_root.is_dir():
            return []
        definitions = []
        for path in sorted(self.definitions_root.glob("*.yml")):
            definitions.append(self._definition_from_dict(yaml.safe_load(path.read_text()) or {}))
        return definitions

    def _load_definition(self, publisher_id: str) -> PublisherDefinition:
        path = self.definitions_root / f"{normalize_slug(publisher_id)}.yml"
        if not path.is_file():
            raise FileNotFoundError(f"Publisher definition not found: {publisher_id}")
        return self._definition_from_dict(yaml.safe_load(path.read_text(encoding="utf-8")) or {})

    def _write_definition(self, definition: PublisherDefinition) -> Path:
        self.definitions_root.mkdir(parents=True, exist_ok=True)
        path = self.definitions_root / f"{definition.id}.yml"
        payload = {
            "schema": PUBLISHER_DEFINITION_SCHEMA,
            "id": definition.id,
            "status": definition.status,
            "schedule": asdict(definition.schedule),
            "target_defaults": definition.target_defaults,
            "targets": {
                target.id: {
                    "source": {
                        "module": target.source.module,
                        "filter": target.source.filter,
                    },
                    "render": asdict(target.render),
                    "target": asdict(target.target),
                }
                for target in definition.targets
            },
        }
        path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), "utf-8")
        return path

    def _load_state(self, publisher_id: str) -> dict[str, PublisherTargetState]:
        path = self.state_root / f"{normalize_slug(publisher_id)}.yml"
        if not path.is_file():
            return {}
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        targets = payload.get("targets") if isinstance(payload, dict) else {}
        if not isinstance(targets, dict):
            return {}
        return {
            str(target_id): PublisherTargetState(
                note_id=str(data.get("note_id") or ""),
                folder_path=str(data.get("folder_path") or ""),
                title=str(data.get("title") or ""),
                content_hash=str(data.get("content_hash") or ""),
                last_synced_at=str(data.get("last_synced_at") or ""),
                last_status=str(data.get("last_status") or ""),
                last_error=str(data.get("last_error") or ""),
            )
            for target_id, data in targets.items()
            if isinstance(data, dict)
        }

    def _write_state(self, publisher_id: str, state: dict[str, PublisherTargetState]) -> Path:
        self.state_root.mkdir(parents=True, exist_ok=True)
        path = self.state_root / f"{normalize_slug(publisher_id)}.yml"
        payload = {
            "schema": PUBLISHER_STATE_SCHEMA,
            "publisher_id": publisher_id,
            "targets": {target_id: asdict(value) for target_id, value in sorted(state.items())},
        }
        path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), "utf-8")
        return path

    def _write_render(self, target_id: str, body: str) -> Path:
        self.renders_root.mkdir(parents=True, exist_ok=True)
        path = self.renders_root / f"{_safe_file_stem(target_id)}.md"
        path.write_text(body.rstrip() + "\n", encoding="utf-8")
        return path

    def _write_run(self, publisher_id: str, payload: dict[str, Any]) -> Path:
        self.runs_root.mkdir(parents=True, exist_ok=True)
        suffix = now_iso().replace(":", "").replace("+", "Z")
        path = self.runs_root / f"{suffix}-{normalize_slug(publisher_id)}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", "utf-8")
        return path

    def _record_event(self, publisher_id: str, payload: dict[str, Any], *, timestamp: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        event = {
            "type": "publisher.run",
            "timestamp": timestamp,
            "publisher": publisher_id,
            "status": payload.get("status"),
            "updated": payload.get("updated"),
            "skipped": payload.get("skipped"),
            "errors": payload.get("errors"),
        }
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _record_target_error(
        self,
        publisher_id: str,
        target_id: str,
        state: dict[str, PublisherTargetState],
        error: PublishError,
        timestamp: str,
    ) -> None:
        previous = state.get(target_id, PublisherTargetState())
        state[target_id] = PublisherTargetState(
            note_id=previous.note_id,
            folder_path=previous.folder_path,
            title=previous.title,
            content_hash=previous.content_hash,
            last_synced_at=previous.last_synced_at,
            last_status="failed",
            last_error=f"{error.code}: {error.message}",
        )
        self._write_state(publisher_id, state)

    def _folder_path(
        self, definition: PublisherDefinition, target: PublisherTargetDefinition
    ) -> str:
        root = str(definition.target_defaults.get("root_folder") or "iCloud/Alcove").strip("/")
        folder = str(target.target.folder or "").strip("/")
        return f"{root}/{folder}" if folder else root

    def _recreate_missing(
        self, definition: PublisherDefinition, target: PublisherTargetDefinition
    ) -> bool:
        if target.target.recreate_missing is not None:
            return target.target.recreate_missing
        return bool(definition.target_defaults.get("recreate_missing", False))

    def _is_due(self, definition: PublisherDefinition, timestamp: str) -> bool:
        state = self._load_state(definition.id)
        if not state:
            return True
        last_values = [value.last_synced_at for value in state.values() if value.last_synced_at]
        if not last_values:
            return True
        latest = max(last_values)
        try:
            latest_at = datetime.fromisoformat(latest)
            current = datetime.fromisoformat(timestamp)
        except ValueError:
            return True
        delta = current - latest_at
        return delta.total_seconds() >= max(definition.schedule.ttl_hours, 1) * 3600

    def _dirty_sources(self, definition: PublisherDefinition) -> set[str]:
        sources = {target.source.module for target in definition.targets if target.source.module}
        return dirty_sources_for_publisher(self.home, definition.id, sources)

    def _definition_from_dict(self, payload: dict[str, Any]) -> PublisherDefinition:
        schedule = payload.get("schedule") if isinstance(payload.get("schedule"), dict) else {}
        targets_payload = payload.get("targets") if isinstance(payload.get("targets"), dict) else {}
        targets = []
        for target_id, raw in targets_payload.items():
            if not isinstance(raw, dict):
                continue
            source = raw.get("source") if isinstance(raw.get("source"), dict) else {}
            render = raw.get("render") if isinstance(raw.get("render"), dict) else {}
            target = raw.get("target") if isinstance(raw.get("target"), dict) else {}
            targets.append(
                PublisherTargetDefinition(
                    id=str(target_id),
                    source=PublisherSource(
                        module=str(source.get("module") or ""),
                        filter=dict(source.get("filter") or {}),
                    ),
                    render=PublisherRender(
                        template=str(render.get("template") or ""),
                        title=str(render.get("title") or target_id),
                    ),
                    target=PublisherTarget(
                        folder=str(target.get("folder") or ""),
                        title=str(target.get("title") or render.get("title") or target_id),
                        type=str(target.get("type") or "apple-notes"),
                        mode=str(target.get("mode") or "replace"),
                        recreate_missing=(
                            bool(target["recreate_missing"])
                            if target.get("recreate_missing") is not None
                            else None
                        ),
                    ),
                )
            )
        return PublisherDefinition(
            id=normalize_slug(str(payload.get("id") or DEFAULT_PUBLISHER_ID)),
            status=str(payload.get("status") or "active"),
            schedule=PublisherSchedule(
                enabled=bool(schedule.get("enabled", True)),
                ttl_hours=max(_int_value(schedule.get("ttl_hours"), 24), 1),
            ),
            target_defaults=dict(payload.get("target_defaults") or {}),
            targets=targets,
        )

    def _default_apple_notes_definition(self, *, root_folder: str) -> PublisherDefinition:
        return PublisherDefinition(
            id=DEFAULT_PUBLISHER_ID,
            target_defaults={
                "type": "apple-notes",
                "root_folder": root_folder,
                "mode": "replace",
                "recreate_missing": False,
            },
            targets=[
                PublisherTargetDefinition(
                    id="pins_regular",
                    source=PublisherSource(
                        module="pins", filter={"kind": "regular", "status": "active"}
                    ),
                    render=PublisherRender(template="pins_digest", title="Regular Pins"),
                    target=PublisherTarget(folder="pins", title="Regular Pins"),
                ),
                PublisherTargetDefinition(
                    id="pins_todo",
                    source=PublisherSource(
                        module="pins", filter={"kind": "todo", "status": "active"}
                    ),
                    render=PublisherRender(template="pins_digest", title="TODO Pins"),
                    target=PublisherTarget(folder="pins", title="TODO Pins"),
                ),
                PublisherTargetDefinition(
                    id="planner_digest",
                    source=PublisherSource(module="tasks", filter={"status": "active"}),
                    render=PublisherRender(template="planner_digest", title="Planner Digest"),
                    target=PublisherTarget(folder="planner", title="Planner Digest"),
                ),
                PublisherTargetDefinition(
                    id="prompt_library",
                    source=PublisherSource(module="prompts", filter={"status": "active"}),
                    render=PublisherRender(template="prompt_library", title="Prompt Library"),
                    target=PublisherTarget(folder="prompts", title="Prompt Library"),
                ),
                PublisherTargetDefinition(
                    id="project_registry",
                    source=PublisherSource(module="projects", filter={}),
                    render=PublisherRender(template="project_registry", title="Project Registry"),
                    target=PublisherTarget(folder="projects", title="Project Registry"),
                ),
            ],
        )

    def _merge_missing_default_targets(
        self, existing: PublisherDefinition, default: PublisherDefinition
    ) -> list[PublisherTargetDefinition]:
        existing_ids = {target.id for target in existing.targets}
        return [target for target in default.targets if target.id not in existing_ids]


class LocalAppleNotesTarget:
    def resolve_or_create(
        self,
        *,
        folder_path: str,
        title: str,
        note_id: str = "",
        recreate_missing: bool = False,
    ) -> TargetRef:
        payload = self._run(
            {
                "action": "resolve-or-create",
                "folder_path": folder_path,
                "title": title,
                "note_id": note_id,
                "recreate_missing": recreate_missing,
            }
        )
        note = payload.get("note") if isinstance(payload.get("note"), dict) else {}
        return TargetRef(
            note_id=str(note.get("id") or ""),
            folder_path=str(note.get("folder_path") or folder_path),
            title=str(note.get("title") or title),
        )

    def replace_note_body(self, *, note_id: str, title: str, body: str) -> dict[str, Any]:
        return self._run(
            {
                "action": "replace-note-body",
                "note_id": note_id,
                "title": title,
                "body_html": _markdown_as_html(body),
            }
        )

    def _run(self, payload: dict[str, Any]) -> dict[str, Any]:
        if platform.system() != "Darwin":
            raise PublishError("APPLE_NOTES_UNAVAILABLE", "Apple Notes publishing requires macOS.")
        osascript = shutil.which("osascript")
        if not osascript:
            raise PublishError("APPLE_NOTES_UNAVAILABLE", "osascript is not available.")
        result = subprocess.run(  # noqa: S603 - fixed osascript executable.
            [osascript, "-l", "JavaScript"],
            input=_apple_notes_jxa(payload),
            text=True,
            capture_output=True,
            check=False,
        )
        combined = (result.stdout or "").strip() or (result.stderr or "").strip()
        if result.returncode != 0:
            if "not authorized" in combined.lower() or "permission" in combined.lower():
                raise PublishError("AUTOMATION_PERMISSION_DENIED", combined)
            raise PublishError(
                "APPLE_NOTES_UNAVAILABLE", combined or "Apple Notes automation failed."
            )
        try:
            parsed = json.loads(combined)
        except json.JSONDecodeError as exc:
            raise PublishError(
                "APPLE_NOTES_UNAVAILABLE", "Apple Notes returned invalid JSON."
            ) from exc
        if not parsed.get("ok"):
            code = str(parsed.get("error") or "APPLE_NOTES_UNAVAILABLE")
            details = str(parsed.get("details") or parsed)
            raise PublishError(code, details)
        data = parsed.get("data")
        return data if isinstance(data, dict) else {}


class FileAppleNotesTarget:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        self.notes_root = self.root / "notes"

    def resolve_or_create(
        self,
        *,
        folder_path: str,
        title: str,
        note_id: str = "",
        recreate_missing: bool = False,
    ) -> TargetRef:
        if note_id:
            path = self._note_path(note_id)
            if path.is_file():
                return TargetRef(note_id=note_id, folder_path=folder_path, title=title)
            if not recreate_missing:
                raise PublishError("TARGET_MISSING", f"Missing note {note_id}")
        matches = self._find_by_folder_title(folder_path, title)
        if len(matches) > 1:
            raise PublishError(
                "TARGET_AMBIGUOUS",
                f"Multiple notes match {title}",
                details={"candidates": matches},
            )
        if len(matches) == 1:
            return TargetRef(note_id=matches[0]["note_id"], folder_path=folder_path, title=title)
        generated = f"note-{sha256(f'{folder_path}\\n{title}'.encode('utf-8')).hexdigest()[:16]}"
        self._write_note(generated, folder_path=folder_path, title=title, body="")
        return TargetRef(note_id=generated, folder_path=folder_path, title=title)

    def replace_note_body(self, *, note_id: str, title: str, body: str) -> dict[str, Any]:
        path = self._note_path(note_id)
        if not path.is_file():
            raise PublishError("TARGET_MISSING", f"Missing note {note_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        self._write_note(
            note_id,
            folder_path=str(payload.get("folder_path") or ""),
            title=title,
            body=body,
        )
        return {"status": "updated", "note_id": note_id}

    def _find_by_folder_title(self, folder_path: str, title: str) -> list[dict[str, str]]:
        matches = []
        for path in sorted(self.notes_root.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("folder_path") == folder_path and payload.get("title") == title:
                matches.append(
                    {
                        "note_id": str(payload.get("note_id") or path.stem),
                        "folder_path": str(payload.get("folder_path") or folder_path),
                        "title": str(payload.get("title") or title),
                    }
                )
        return matches

    def _write_note(self, note_id: str, *, folder_path: str, title: str, body: str) -> None:
        self.notes_root.mkdir(parents=True, exist_ok=True)
        self._note_path(note_id).write_text(
            json.dumps(
                {
                    "note_id": note_id,
                    "folder_path": folder_path,
                    "title": title,
                    "body": body,
                    "updated_at": now_iso(),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _note_path(self, note_id: str) -> Path:
        return self.notes_root / f"{_safe_file_stem(note_id)}.json"


def _apple_notes_jxa(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False)
    return f"""
function ok(data) {{
  return JSON.stringify({{ ok: true, data }});
}}

function fail(error, details) {{
  return JSON.stringify({{ ok: false, error, details }});
}}

function folderPathParts(path) {{
  return String(path || '').split('/').map((part) => part.trim()).filter(Boolean);
}}

function scanFolderNotes(folder, accountName, parentPath, out) {{
  const folderPath = parentPath ? `${{parentPath}}/${{folder.name()}}` : `${{accountName}}/${{folder.name()}}`;
  try {{
    for (const note of folder.notes()) {{
      out.push({{ note, folderPath }});
    }}
  }} catch (error) {{
  }}
  let children = [];
  try {{
    children = folder.folders();
  }} catch (error) {{
    children = [];
  }}
  for (const child of children) {{
    try {{
      scanFolderNotes(child, accountName, folderPath, out);
    }} catch (error) {{
    }}
  }}
}}

function allNotes(app) {{
  const out = [];
  for (const account of app.accounts()) {{
    const accountName = account.name();
    for (const folder of account.folders()) {{
      scanFolderNotes(folder, accountName, '', out);
    }}
  }}
  return out;
}}

function findNoteById(app, noteId) {{
  if (!noteId) return null;
  for (const row of allNotes(app)) {{
    if (row.note.id() === noteId) return row;
  }}
  return null;
}}

function ensureFolder(app, folderPath) {{
  const parts = folderPathParts(folderPath);
  if (parts.length < 2) throw new Error(`Invalid folder path: ${{folderPath}}`);
  let current = app.accounts.byName(parts[0]);
  for (let index = 1; index < parts.length; index += 1) {{
    const name = parts[index];
    let found = null;
    for (const folder of current.folders()) {{
      if (folder.name() === name) {{
        found = folder;
        break;
      }}
    }}
    if (!found) {{
      const created = app.Folder({{ name }});
      current.folders.push(created);
      found = current.folders.byName(name);
    }}
    current = found;
  }}
  return current;
}}

function notesInFolder(app, folderPath, title) {{
  return allNotes(app).filter((row) => row.folderPath === folderPath && row.note.name() === title);
}}

function allNotesInFolder(app, folderPath) {{
  return allNotes(app).filter((row) => row.folderPath === folderPath);
}}

function main() {{
  const params = JSON.parse({json.dumps(encoded)});
  const action = params.action;
  const app = Application('Notes');
  try {{
    if (action === 'resolve-or-create') {{
      const folderPath = params.folder_path;
      const title = params.title;
      const existing = findNoteById(app, params.note_id || '');
      if (existing) {{
        return ok({{ note: {{ id: existing.note.id(), title, folder_path: existing.folderPath }} }});
      }}
      if (params.note_id && !params.recreate_missing) {{
        return fail('TARGET_MISSING', `Missing note ${{params.note_id}}`);
      }}
      const folder = ensureFolder(app, folderPath);
      const matches = notesInFolder(app, folderPath, title);
      if (matches.length > 1) {{
        return fail('TARGET_AMBIGUOUS', `Multiple notes match ${{title}} in ${{folderPath}}`);
      }}
      if (matches.length === 1) {{
        return ok({{ note: {{ id: matches[0].note.id(), title, folder_path: folderPath }} }});
      }}
      const beforeIds = new Set(allNotesInFolder(app, folderPath).map((row) => row.note.id()));
      const note = app.Note({{ body: `<div>${{title}}</div>` }});
      folder.notes.push(note);
      const createdRows = allNotesInFolder(app, folderPath).filter(
        (row) => !beforeIds.has(row.note.id())
      );
      if (createdRows.length !== 1) {{
        return fail('APPLE_NOTES_UNAVAILABLE', `Expected one created note, found ${{createdRows.length}}`);
      }}
      const created = app.notes.byId(createdRows[0].note.id());
      created.name = title;
      return ok({{ note: {{ id: created.id(), title: created.name(), folder_path: folderPath }} }});
    }}
    if (action === 'replace-note-body') {{
      const row = findNoteById(app, params.note_id || '');
      if (!row) return fail('TARGET_MISSING', `Missing note ${{params.note_id}}`);
      const note = app.notes.byId(row.note.id());
      note.body = params.body_html;
      note.name = params.title;
      return ok({{ note: {{ id: note.id(), title: note.name(), folder_path: row.folderPath }} }});
    }}
    return fail('UNSUPPORTED_ACTION', action);
  }} catch (error) {{
    const details = String(error.message || error);
    if (details.toLowerCase().includes('not authorized')) {{
      return fail('AUTOMATION_PERMISSION_DENIED', details);
    }}
    return fail('APPLE_NOTES_UNAVAILABLE', details);
  }}
}}

main();
"""


def _int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_file_stem(value: str) -> str:
    return str(value or "item").replace("/", "-").replace("\\", "-")
