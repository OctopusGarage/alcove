from __future__ import annotations

from dataclasses import asdict
from typing import Any

from alcove.classify import ClassifyModule
from alcove.connectors.apple_notes import AppleNotesConnector, AppleNotesImportRequest
from alcove.connectors.fetch import ConnectorFetchModule
from alcove.connectors.github_stars import GitHubStarsConnector, GitHubStarsImportRequest
from alcove.doctor import DoctorModule
from alcove.exporter import ExportModule
from alcove.gardener import GardenerModule
from alcove.inbox import InboxModule
from alcove.inbox_models import InboxNoteRequest, InboxProcessResult
from alcove.installer import InstallerModule
from alcove.knowledge import (
    AddConceptRequest,
    AddEntityRequest,
    AddQuestionRequest,
    KnowledgeModule,
    NoteSourceRequest,
)
from alcove.lifecycle import LifecycleModule
from alcove.linking import LinkSourceRequest, LinkingModule
from alcove.mounts import AddMountRequest, MountsModule
from alcove.pins import AddPinRequest, Pin, PinsModule
from alcove.runtime import AlcoveRuntime
from alcove.search import SearchModule, SearchRequest
from alcove.tasks import AddIdeaRequest, AddRoutineRequest, AddTaskRequest, TasksModule
from alcove.taxonomy import load_taxonomy, split_domain_topic
from alcove.validate import ValidateModule


class _Capability:
    def __init__(self, runtime: AlcoveRuntime) -> None:
        self.runtime = runtime


class _SearchCapabilities(_Capability):
    def search(self, request: SearchRequest) -> list[dict[str, Any]]:
        return SearchModule(self.runtime.workspace, home=self.runtime.home).search(request)

    def search_payload(self, request: SearchRequest) -> dict[str, Any]:
        results = self.search(request)
        return self.runtime.scope_payload({"count": len(results), "results": results})

    def search_tags_payload(self) -> dict[str, Any]:
        rows = SearchModule(self.runtime.workspace, home=self.runtime.home).tags()
        return self.runtime.scope_payload({"count": len(rows), "tags": rows})

    def search_tag_doctor_payload(self) -> dict[str, Any]:
        rows = SearchModule(self.runtime.workspace, home=self.runtime.home).tag_doctor()
        return self.runtime.scope_payload({"count": len(rows), "issues": rows})

    def search_recent_payload(self, limit: int = 20) -> dict[str, Any]:
        rows = SearchModule(self.runtime.workspace, home=self.runtime.home).recent(limit)
        return self.runtime.scope_payload({"count": len(rows), "results": rows})

    def search_unindexed_payload(self) -> dict[str, Any]:
        return _SystemCapabilities(self.runtime).validate_payload(strict_quality=False)


class _SystemCapabilities(_Capability):
    def doctor_payload(self) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        return self.runtime.scope_payload(DoctorModule(workspace).check())

    def install_payload(
        self,
        targets: list[str],
        *,
        status: bool = False,
        uninstall: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        installer = InstallerModule(workspace, home=self.runtime.home)
        return self._install_payload(
            installer, targets, status=status, uninstall=uninstall, dry_run=dry_run
        )

    def global_install_payload(
        self,
        targets: list[str],
        *,
        status: bool = False,
        uninstall: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        installer = InstallerModule(None, home=self.runtime.home)
        result = self._install_payload(
            installer,
            targets,
            status=status,
            uninstall=uninstall,
            dry_run=dry_run,
        )
        return {"profile": "global-lite", **result}

    def export_global_payload(self, output_dir: str) -> dict[str, Any]:
        if self.runtime.home is None:
            raise ValueError("Alcove home is required")
        return self.runtime.scope_payload(ExportModule(self.runtime.home).export_global(output_dir))

    def export_kb_payload(self, kb: str, output_dir: str) -> dict[str, Any]:
        if self.runtime.home is None:
            raise ValueError("Alcove home is required")
        return self.runtime.scope_payload(ExportModule(self.runtime.home).export_kb(kb, output_dir))

    def export_all_payload(self, output_dir: str) -> dict[str, Any]:
        if self.runtime.home is None:
            raise ValueError("Alcove home is required")
        return self.runtime.scope_payload(ExportModule(self.runtime.home).export_all(output_dir))

    def validate_payload(self, strict_quality: bool = False) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        issues = ValidateModule(workspace).validate(strict_quality=strict_quality)
        return self.runtime.scope_payload({"issues": issues})

    def gardener_payload(self, prune: bool = False) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        report = GardenerModule(workspace).gardener(prune=prune)
        return self.runtime.scope_payload({"issues": report.issues, "actions": report.actions})

    def _install_payload(
        self,
        installer: InstallerModule,
        targets: list[str],
        *,
        status: bool,
        uninstall: bool,
        dry_run: bool,
    ) -> dict[str, Any]:
        if status:
            return installer.status(targets)
        if uninstall:
            return installer.uninstall(targets, dry_run=dry_run)
        return installer.install(targets, dry_run=dry_run)


class _InboxCapabilities(_Capability):
    def inbox_peek_payload(self) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        item = InboxModule(workspace).peek()
        return self.runtime.scope_payload({"item": asdict(item) if item is not None else None})

    def inbox_read_payload(self, name: str) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        post = InboxModule(workspace).read(name)
        return self.runtime.scope_payload({"item": asdict(post)})

    def inbox_classify_payload(self, name: str, topic: str | None = None) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        return self.runtime.scope_payload(asdict(ClassifyModule(workspace).classify(name, topic)))

    def inbox_archive_payload(
        self,
        name: str,
        topic: str,
        *,
        summary: str = "",
        tags: list[str] | None = None,
        no_auto_tags: bool = False,
        supersede_similar: bool = False,
        validate: bool = False,
    ) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        result = InboxModule(workspace).archive(
            name,
            topic,
            summary=summary,
            tags=tags,
            no_auto_tags=no_auto_tags,
            supersede_similar=supersede_similar,
        )
        return self._process_payload(result, validate=validate)

    def inbox_note_payload(
        self, request: InboxNoteRequest, *, validate: bool = False
    ) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        result = InboxModule(workspace).note(request)
        return self._process_payload(result, validate=validate)

    def inbox_manual_add_payload(
        self, title: str, content: str, source: str = ""
    ) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        return self.runtime.scope_payload(
            InboxModule(workspace).add_manual(title=title, content=content, source=source)
        )

    def inbox_todo_payload(self, name: str, reason: str = "") -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        path = InboxModule(workspace).todo(name, reason)
        return self.runtime.scope_payload({"status": "todo", "path": str(path)})

    def inbox_delete_payload(self, name: str, *, confirm: bool = False) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        return self.runtime.scope_payload(InboxModule(workspace).delete(name, confirm=confirm))

    def _process_payload(
        self, result: InboxProcessResult, *, validate: bool = False
    ) -> dict[str, Any]:
        payload = {
            "archive": str(result.archive_path),
            "source": str(result.source_path),
            "concept": str(result.concept_path) if result.concept_path else "",
            "tags": result.tags,
            "confidence": result.confidence,
            "superseded": result.superseded,
        }
        if validate:
            payload["validation"] = _SystemCapabilities(self.runtime).validate_payload(
                strict_quality=False
            )["issues"]
        return self.runtime.scope_payload(payload)


class _ExternalCapabilities(_Capability):
    def mount_list_payload(self, status: str = "active") -> dict[str, Any]:
        mounts = [
            asdict(mount)
            for mount in MountsModule(self.runtime.workspace, home=self.runtime.home).list(status)
        ]
        return self.runtime.scope_payload({"count": len(mounts), "mounts": mounts})

    def mount_add_payload(self, request: AddMountRequest) -> dict[str, Any]:
        mount = MountsModule(self.runtime.workspace, home=self.runtime.home).add(request)
        return self.runtime.scope_payload({"status": "mounted", "mount": asdict(mount)})

    def mount_scan_payload(self, mount_id: str | None = None) -> dict[str, Any]:
        report = MountsModule(self.runtime.workspace, home=self.runtime.home).scan(mount_id)
        return self.runtime.scope_payload(report)

    def apple_notes_index_payload(self, request: AppleNotesImportRequest) -> dict[str, Any]:
        report = AppleNotesConnector(
            self.runtime.workspace,
            home=self.runtime.home,
        ).import_export(request)
        return self.runtime.scope_payload(report)

    def github_stars_index_payload(self, request: GitHubStarsImportRequest) -> dict[str, Any]:
        report = GitHubStarsConnector(
            self.runtime.workspace,
            home=self.runtime.home,
        ).import_export(request)
        return self.runtime.scope_payload(report)

    def connector_fetch_payload(self, item_path: str) -> dict[str, Any]:
        return self.runtime.scope_payload(
            ConnectorFetchModule(self.runtime.workspace, home=self.runtime.home).fetch(item_path)
        )

    def link_source_payload(self, request: LinkSourceRequest) -> dict[str, Any]:
        return LinkingModule(
            self.runtime.require_workspace(),
            home=self.runtime.home,
        ).link_source(request)


class _ManagedKnowledgeCapabilities(_Capability):
    def note_source_payload(self, request: NoteSourceRequest) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        result = KnowledgeModule(workspace).note_source(request)
        return self.runtime.scope_payload(
            {
                "status": "noted",
                "source_path": str(result.source_path),
                "concept_path": str(result.concept_path) if result.concept_path else "",
            }
        )

    def knowledge_add_concept_payload(self, request: AddConceptRequest) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        result = KnowledgeModule(workspace).add_concept(request)
        return self.runtime.scope_payload({"status": "noted", "okf_concept": str(result.path)})

    def knowledge_add_question_payload(self, request: AddQuestionRequest) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        result = KnowledgeModule(workspace).add_question(request)
        return self.runtime.scope_payload({"status": "added", "okf_question": str(result.path)})

    def knowledge_add_entity_payload(self, request: AddEntityRequest) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        result = KnowledgeModule(workspace).add_entity(request)
        return self.runtime.scope_payload({"status": "added", "okf_entity": str(result.path)})

    def knowledge_promote_payload(
        self, source: str, topic: str = "", summary: str = ""
    ) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        result = KnowledgeModule(workspace).promote_source(source, topic=topic, summary=summary)
        return self.runtime.scope_payload({"status": "promoted", "okf_concept": str(result.path)})

    def knowledge_refresh_payload(
        self,
        topic: str,
        *,
        in_place: bool = False,
        summary: str = "",
    ) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        result = LifecycleModule(workspace).refresh_topic(topic, in_place=in_place, summary=summary)
        return self.runtime.scope_payload(result)

    def knowledge_topics_payload(self) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        classifier = ClassifyModule(workspace)
        return self.runtime.scope_payload(
            {
                "topics": classifier.list_topics(),
                "tags": classifier.list_tags(),
                "domains": classifier.taxonomy.get("domains", {}),
            }
        )

    def topic_payload(self, topic: str, limit: int = 20) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        taxonomy = load_taxonomy(workspace.paths().knowledge)
        domain, topic_slug = split_domain_topic(topic, taxonomy)
        rows = _SearchCapabilities(self.runtime).search(
            SearchRequest(topic=f"{domain}/{topic_slug}", status="active", limit=limit)
        )
        return self.runtime.scope_payload(
            {
                "domain": domain,
                "topic": topic_slug,
                "count": len(rows),
                "results": rows,
            }
        )


class _GlobalHomeCapabilities(_Capability):
    def pin_add_payload(self, request: AddPinRequest) -> dict[str, Any]:
        result = PinsModule(self.runtime.workspace, home=self.runtime.home).add(request)
        return self.runtime.scope_payload(
            {
                "status": "pinned",
                "path": str(result.path),
                "pin": _pin_dict(result.pin),
            }
        )

    def pin_list_payload(self, tag: str | None = None, status: str = "active") -> dict[str, Any]:
        pins = [
            _pin_dict(pin)
            for pin in PinsModule(self.runtime.workspace, home=self.runtime.home).list(tag, status)
        ]
        return self.runtime.scope_payload({"count": len(pins), "pins": pins})

    def pin_archive_payload(self, pin_id: str, confirm: bool = False) -> dict[str, Any]:
        payload = PinsModule(self.runtime.workspace, home=self.runtime.home).archive(
            pin_id,
            confirm=confirm,
        )
        return self.runtime.scope_payload(payload)

    def task_add_payload(self, request: AddTaskRequest) -> dict[str, Any]:
        task = TasksModule(self.runtime.workspace, home=self.runtime.home).task_add(request)
        return self.runtime.scope_payload({"status": "added", "task": asdict(task)})

    def idea_add_payload(self, request: AddIdeaRequest) -> dict[str, Any]:
        idea = TasksModule(self.runtime.workspace, home=self.runtime.home).idea_add(request)
        return self.runtime.scope_payload({"status": "added", "idea": asdict(idea)})

    def idea_list_payload(self, status: str = "active") -> dict[str, Any]:
        ideas = [
            asdict(idea)
            for idea in TasksModule(self.runtime.workspace, home=self.runtime.home).idea_list(
                status
            )
        ]
        return self.runtime.scope_payload({"count": len(ideas), "ideas": ideas})

    def task_list_payload(self, status: str = "pending") -> dict[str, Any]:
        tasks = [
            asdict(task)
            for task in TasksModule(self.runtime.workspace, home=self.runtime.home).task_list(
                status
            )
        ]
        return self.runtime.scope_payload({"count": len(tasks), "tasks": tasks})

    def task_complete_payload(self, task_id: str) -> dict[str, Any]:
        task = TasksModule(self.runtime.workspace, home=self.runtime.home).task_complete(task_id)
        return self.runtime.scope_payload({"status": "completed", "task": asdict(task)})

    def task_cancel_payload(self, task_id: str) -> dict[str, Any]:
        task = TasksModule(self.runtime.workspace, home=self.runtime.home).task_cancel(task_id)
        return self.runtime.scope_payload({"status": "cancelled", "task": asdict(task)})

    def idea_promote_payload(
        self,
        idea_id: str,
        priority: str = "medium",
        due: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        tasks = TasksModule(self.runtime.workspace, home=self.runtime.home)
        task = tasks.idea_promote_to_task(
            idea_id,
            priority=priority,
            due=due,
            notes=notes,
        )
        idea = next(
            item for item in tasks.idea_list(status="promoted") if item.promoted_task_id == task.id
        )
        return self.runtime.scope_payload(
            {
                "status": "promoted",
                "idea": asdict(idea),
                "task": asdict(task),
            }
        )

    def routine_add_payload(self, request: AddRoutineRequest) -> dict[str, Any]:
        routine = TasksModule(self.runtime.workspace, home=self.runtime.home).routine_add(request)
        return self.runtime.scope_payload({"status": "added", "routine": asdict(routine)})

    def routine_list_payload(self, status: str = "active") -> dict[str, Any]:
        routines = [
            asdict(routine)
            for routine in TasksModule(self.runtime.workspace, home=self.runtime.home).routine_list(
                status
            )
        ]
        return self.runtime.scope_payload({"count": len(routines), "routines": routines})

    def routine_materialize_due_payload(self, today: str = "") -> dict[str, Any]:
        created = TasksModule(
            self.runtime.workspace,
            home=self.runtime.home,
        ).routine_materialize_due(today=today or None)
        return self.runtime.scope_payload(
            {"status": "materialized", "created": [asdict(task) for task in created]}
        )


def _pin_dict(pin: Pin) -> dict[str, Any]:
    return {
        "id": pin.id,
        "title": pin.title,
        "description": pin.description,
        "tags": pin.tags,
        "status": pin.status,
        "priority": pin.priority,
        "source_refs": pin.source_refs,
        "path": str(pin.path),
    }
