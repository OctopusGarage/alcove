from __future__ import annotations

from dataclasses import asdict
from typing import Any

from alcove.application_base import _Capability
from alcove.paths import compact_user_path
from alcove.pins import AddPinRequest, Pin, PinsModule, UpdatePinRequest
from alcove.projects import AddProjectRequest, ProjectRecord, ProjectsModule
from alcove.prompts import AddPromptRequest, Prompt, PromptsModule
from alcove.tasks import AddIdeaRequest, AddRoutineRequest, AddTaskRequest, TasksModule


class _GlobalHomeCapabilities(_Capability):
    def pin_add_payload(self, request: AddPinRequest) -> dict[str, Any]:
        result = PinsModule(self.runtime.workspace, home=self.runtime.home).add(request)
        self._record_action(
            area="pin",
            action="pin.add",
            summary=f"Pinned: {result.pin.title}",
            metadata={"id": result.pin.id, "kind": result.pin.kind},
        )
        return self.runtime.scope_payload(
            {
                "status": "pinned",
                "path": str(result.path),
                "pin": _pin_dict(result.pin),
            }
        )

    def pin_list_payload(self, tag: str | None = None, status: str = "active") -> dict[str, Any]:
        module = PinsModule(self.runtime.workspace, home=self.runtime.home)
        pins = [_pin_dict(pin) for pin in module.list(tag, status)]
        return self.runtime.scope_payload({"count": len(pins), "pins": pins})

    def pin_get_payload(self, pin_id: str) -> dict[str, Any]:
        pin = PinsModule(self.runtime.workspace, home=self.runtime.home).get(pin_id)
        return self.runtime.scope_payload({"pin": _pin_dict(pin)})

    def pin_search_payload(
        self,
        query: str = "",
        kind: str = "",
        tag: str = "",
        status: str = "active",
    ) -> dict[str, Any]:
        module = PinsModule(self.runtime.workspace, home=self.runtime.home)
        matches = module.search(
            query=query,
            kind=kind,
            tag=tag,
            status=status,
        )
        pins = [_pin_dict(pin) for pin in matches]
        return self.runtime.scope_payload({"count": len(pins), "pins": pins})

    def pin_update_payload(self, request: UpdatePinRequest) -> dict[str, Any]:
        result = PinsModule(self.runtime.workspace, home=self.runtime.home).update(request)
        self._record_action(
            area="pin",
            action="pin.update",
            summary=f"Updated pin: {result.pin.title}",
            metadata={"id": result.pin.id, "kind": result.pin.kind},
        )
        return self.runtime.scope_payload(
            {
                "status": "updated",
                "path": str(result.path),
                "index_path": str(result.index_path),
                "pin": _pin_dict(result.pin),
            }
        )

    def pin_rebuild_index_payload(self) -> dict[str, Any]:
        module = PinsModule(self.runtime.workspace, home=self.runtime.home)
        path = module.rebuild_index()
        return self.runtime.scope_payload(
            {"status": "rebuilt", "index_path": str(path), "count": len(module.list(status=""))}
        )

    def pin_render_html_payload(self, output_path: str = "") -> dict[str, Any]:
        path = PinsModule(self.runtime.workspace, home=self.runtime.home).render_html(
            output_path or None
        )
        return self.runtime.scope_payload({"status": "rendered", "path": str(path)})

    def pin_archive_payload(self, pin_id: str, confirm: bool = False) -> dict[str, Any]:
        payload = PinsModule(self.runtime.workspace, home=self.runtime.home).archive(
            pin_id,
            confirm=confirm,
        )
        self._record_action(
            area="pin",
            action="pin.archive",
            summary=f"Archived pin: {pin_id}",
            metadata={"id": pin_id},
        )
        return self.runtime.scope_payload(payload)

    def project_add_payload(self, request: AddProjectRequest) -> dict[str, Any]:
        project = ProjectsModule(self.runtime.workspace, home=self.runtime.home).add(request)
        self._record_action(
            area="project",
            action="project.add",
            summary=f"Added project: {project.alias}",
            metadata={"alias": project.alias},
        )
        return self.runtime.scope_payload({"status": "added", "project": _project_dict(project)})

    def project_get_payload(self, alias: str) -> dict[str, Any]:
        project = ProjectsModule(self.runtime.workspace, home=self.runtime.home).get(alias)
        return self.runtime.scope_payload({"project": _project_dict(project)})

    def project_list_payload(self) -> dict[str, Any]:
        projects = [
            _project_dict(project)
            for project in ProjectsModule(self.runtime.workspace, home=self.runtime.home).list()
        ]
        return self.runtime.scope_payload({"count": len(projects), "projects": projects})

    def project_find_payload(self, keyword: str) -> dict[str, Any]:
        projects = [
            _project_dict(project)
            for project in ProjectsModule(self.runtime.workspace, home=self.runtime.home).find(
                keyword
            )
        ]
        return self.runtime.scope_payload({"count": len(projects), "projects": projects})

    def project_remove_payload(self, alias: str) -> dict[str, Any]:
        payload = ProjectsModule(self.runtime.workspace, home=self.runtime.home).remove(alias)
        self._record_action(
            area="project",
            action="project.remove",
            summary=f"Removed project: {alias}",
            metadata={"alias": alias},
        )
        return self.runtime.scope_payload(payload)

    def project_roots_set_payload(self, roots: list[str]) -> dict[str, Any]:
        payload = ProjectsModule(self.runtime.workspace, home=self.runtime.home).configure_roots(
            roots
        )
        return self.runtime.scope_payload(payload)

    def prompt_save_payload(self, request: AddPromptRequest) -> dict[str, Any]:
        result = PromptsModule(self.runtime.workspace, home=self.runtime.home).save(request)
        self._record_action(
            area="prompt",
            action="prompt.save",
            summary=f"Saved prompt: {result.prompt.title}",
            metadata={"id": result.prompt.id},
        )
        return self.runtime.scope_payload(
            {
                "status": "saved",
                "path": compact_user_path(result.path),
                "index_path": compact_user_path(result.index_path),
                "prompt": _prompt_dict(result.prompt),
            }
        )

    def prompt_search_payload(
        self,
        query: str = "",
        tag: str = "",
        status: str = "active",
    ) -> dict[str, Any]:
        prompts = [
            _prompt_dict(prompt)
            for prompt in PromptsModule(self.runtime.workspace, home=self.runtime.home).search(
                query=query,
                tag=tag,
                status=status,
            )
        ]
        return self.runtime.scope_payload({"count": len(prompts), "prompts": prompts})

    def prompt_get_payload(self, prompt_id: str) -> dict[str, Any]:
        prompt = PromptsModule(self.runtime.workspace, home=self.runtime.home).get(prompt_id)
        return self.runtime.scope_payload({"prompt": _prompt_dict(prompt)})

    def prompt_archive_payload(self, prompt_id: str, confirm: bool = False) -> dict[str, Any]:
        payload = PromptsModule(self.runtime.workspace, home=self.runtime.home).archive(
            prompt_id,
            confirm=confirm,
        )
        self._record_action(
            area="prompt",
            action="prompt.archive",
            summary=f"Archived prompt: {prompt_id}",
            metadata={"id": prompt_id},
        )
        return self.runtime.scope_payload(payload)

    def prompt_tags_payload(self) -> dict[str, Any]:
        tags = PromptsModule(self.runtime.workspace, home=self.runtime.home).tags()
        return self.runtime.scope_payload({"count": len(tags), "tags": tags})

    def prompt_rebuild_index_payload(self) -> dict[str, Any]:
        module = PromptsModule(self.runtime.workspace, home=self.runtime.home)
        path = module.rebuild_index()
        return self.runtime.scope_payload(
            {
                "status": "rebuilt",
                "index_path": compact_user_path(path),
                "count": len(module.list(status="")),
            }
        )

    def task_add_payload(self, request: AddTaskRequest) -> dict[str, Any]:
        task = TasksModule(self.runtime.workspace, home=self.runtime.home).task_add(request)
        self._record_action(
            area="task",
            action="task.add",
            summary=f"Added task: {task.title}",
            metadata={"id": task.id, "priority": task.priority},
        )
        return self.runtime.scope_payload({"status": "added", "task": asdict(task)})

    def idea_add_payload(self, request: AddIdeaRequest) -> dict[str, Any]:
        idea = TasksModule(self.runtime.workspace, home=self.runtime.home).idea_add(request)
        self._record_action(
            area="task",
            action="idea.add",
            summary=f"Added idea: {idea.title}",
            metadata={"id": idea.id},
        )
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

    def task_edit_payload(
        self,
        task_id: str,
        *,
        title: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
        priority: str | None = None,
        due: str | None = None,
    ) -> dict[str, Any]:
        task = TasksModule(self.runtime.workspace, home=self.runtime.home).task_edit(
            task_id,
            title=title,
            notes=notes,
            tags=tags,
            priority=priority,
            due=due,
        )
        self._record_action(
            area="task",
            action="task.edit",
            summary=f"Edited task: {task.title}",
            metadata={"id": task.id},
        )
        return self.runtime.scope_payload({"status": "updated", "task": asdict(task)})

    def task_complete_payload(self, task_id: str) -> dict[str, Any]:
        task = TasksModule(self.runtime.workspace, home=self.runtime.home).task_complete(task_id)
        self._record_action(
            area="task",
            action="task.complete",
            summary=f"Completed task: {task.title}",
            metadata={"id": task.id},
        )
        return self.runtime.scope_payload({"status": "completed", "task": asdict(task)})

    def task_cancel_payload(self, task_id: str) -> dict[str, Any]:
        task = TasksModule(self.runtime.workspace, home=self.runtime.home).task_cancel(task_id)
        self._record_action(
            area="task",
            action="task.cancel",
            summary=f"Cancelled task: {task.title}",
            metadata={"id": task.id},
        )
        return self.runtime.scope_payload({"status": "cancelled", "task": asdict(task)})

    def idea_edit_payload(
        self,
        idea_id: str,
        *,
        title: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        idea = TasksModule(self.runtime.workspace, home=self.runtime.home).idea_edit(
            idea_id,
            title=title,
            notes=notes,
            tags=tags,
        )
        self._record_action(
            area="task",
            action="idea.edit",
            summary=f"Edited idea: {idea.title}",
            metadata={"id": idea.id},
        )
        return self.runtime.scope_payload({"status": "updated", "idea": asdict(idea)})

    def idea_archive_payload(self, idea_id: str) -> dict[str, Any]:
        idea = TasksModule(self.runtime.workspace, home=self.runtime.home).idea_archive(idea_id)
        self._record_action(
            area="task",
            action="idea.archive",
            summary=f"Archived idea: {idea.title}",
            metadata={"id": idea.id},
        )
        return self.runtime.scope_payload({"status": "archived", "idea": asdict(idea)})

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

    def idea_promote_routine_payload(
        self,
        idea_id: str,
        *,
        priority: str = "medium",
        next_due: str = "",
        notes: str = "",
        schedule: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        tasks = TasksModule(self.runtime.workspace, home=self.runtime.home)
        routine = tasks.idea_promote_to_routine(
            idea_id,
            priority=priority,
            next_due=next_due,
            notes=notes,
            schedule=schedule or {},
        )
        idea = next(
            item
            for item in tasks.idea_list(status="promoted")
            if item.promoted_routine_id == routine.id
        )
        self._record_action(
            area="task",
            action="idea.promote_routine",
            summary=f"Promoted idea to routine: {routine.title}",
            metadata={"idea_id": idea.id, "routine_id": routine.id},
        )
        return self.runtime.scope_payload(
            {"status": "promoted", "idea": asdict(idea), "routine": asdict(routine)}
        )

    def routine_add_payload(self, request: AddRoutineRequest) -> dict[str, Any]:
        routine = TasksModule(self.runtime.workspace, home=self.runtime.home).routine_add(request)
        self._record_action(
            area="task",
            action="routine.add",
            summary=f"Added routine: {routine.title}",
            metadata={"id": routine.id},
        )
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
        self._record_action(
            area="task",
            action="routine.materialize_due",
            summary="Materialized due routines",
            metrics={"created": len(created)},
            metadata={"today": today},
        )
        return self.runtime.scope_payload(
            {"status": "materialized", "created": [asdict(task) for task in created]}
        )

    def routine_edit_payload(
        self,
        routine_id: str,
        *,
        title: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
        priority: str | None = None,
        schedule: dict[str, Any] | None = None,
        next_due: str | None = None,
    ) -> dict[str, Any]:
        routine = TasksModule(self.runtime.workspace, home=self.runtime.home).routine_edit(
            routine_id,
            title=title,
            notes=notes,
            tags=tags,
            priority=priority,
            schedule=schedule,
            next_due=next_due,
        )
        self._record_action(
            area="task",
            action="routine.edit",
            summary=f"Edited routine: {routine.title}",
            metadata={"id": routine.id},
        )
        return self.runtime.scope_payload({"status": "updated", "routine": asdict(routine)})

    def routine_pause_payload(self, routine_id: str) -> dict[str, Any]:
        routine = TasksModule(self.runtime.workspace, home=self.runtime.home).routine_pause(
            routine_id
        )
        self._record_action(
            area="task",
            action="routine.pause",
            summary=f"Paused routine: {routine.title}",
            metadata={"id": routine.id},
        )
        return self.runtime.scope_payload({"status": "paused", "routine": asdict(routine)})

    def routine_resume_payload(self, routine_id: str, today: str = "") -> dict[str, Any]:
        routine = TasksModule(self.runtime.workspace, home=self.runtime.home).routine_resume(
            routine_id,
            today=today or None,
        )
        self._record_action(
            area="task",
            action="routine.resume",
            summary=f"Resumed routine: {routine.title}",
            metadata={"id": routine.id},
        )
        return self.runtime.scope_payload({"status": "active", "routine": asdict(routine)})

    def routine_archive_payload(self, routine_id: str) -> dict[str, Any]:
        routine = TasksModule(self.runtime.workspace, home=self.runtime.home).routine_archive(
            routine_id
        )
        self._record_action(
            area="task",
            action="routine.archive",
            summary=f"Archived routine: {routine.title}",
            metadata={"id": routine.id},
        )
        return self.runtime.scope_payload({"status": "archived", "routine": asdict(routine)})

    def task_digest_payload(
        self,
        *,
        period: str = "weekly",
        today: str = "",
        notify: bool = False,
    ) -> dict[str, Any]:
        payload = TasksModule(self.runtime.workspace, home=self.runtime.home).task_digest(
            period=period,
            today=today or None,
            notify=notify,
        )
        self._record_action(
            area="task",
            action="task.digest",
            summary=f"Built task digest: {period}",
            metadata={"period": period, "notified": bool(notify)},
            visible=False,
        )
        return self.runtime.scope_payload(payload)

    def task_import_social_radar_payload(self, source: str) -> dict[str, Any]:
        result = TasksModule(
            self.runtime.workspace,
            home=self.runtime.home,
        ).import_social_radar(source)
        return self.runtime.scope_payload({"status": "imported", **result})


def _pin_dict(pin: Pin) -> dict[str, Any]:
    return {
        "id": pin.id,
        "title": pin.title,
        "description": pin.description,
        "summary": pin.summary,
        "content": pin.content,
        "kind": pin.kind,
        "tags": pin.tags,
        "status": pin.status,
        "priority": pin.priority,
        "source_refs": pin.source_refs,
        "resources": pin.resources,
        "content_format": pin.content_format,
        "path": f"pins/{pin.path.name}",
        "created_at": pin.created_at,
        "updated_at": pin.updated_at,
        "last_used_at": pin.last_used_at,
    }


def _project_dict(project: ProjectRecord) -> dict[str, Any]:
    path_label = project.path.expanduser().name or compact_user_path(project.path)
    return {
        "alias": project.alias,
        "path": compact_user_path(project.path),
        "path_label": path_label,
        "target_label": f"{project.alias} ({path_label})",
        "command_hint": f"alcove project get {project.alias} --json",
        "note": project.note,
        "exists": project.exists,
        "source": project.source,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


def _prompt_dict(prompt: Prompt) -> dict[str, Any]:
    return {
        "id": prompt.id,
        "title": prompt.title,
        "description": prompt.description,
        "content": prompt.content,
        "tags": prompt.tags,
        "use_cases": prompt.use_cases,
        "source_refs": prompt.source_refs,
        "status": prompt.status,
        "path": f"prompts/{prompt.path.name}",
        "created_at": prompt.created_at,
        "updated_at": prompt.updated_at,
    }
