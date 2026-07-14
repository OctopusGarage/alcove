from __future__ import annotations

from typing import Any

from alcove.application_global_planner import _GlobalPlannerCapabilities
from alcove.application_global_prompts import _GlobalPromptCapabilities
from alcove.paths import compact_user_path
from alcove.pins import AddPinRequest, Pin, PinsModule, UpdatePinRequest
from alcove.projects import AddProjectRequest, ProjectRecord, ProjectsModule


class _GlobalHomeCapabilities(_GlobalPromptCapabilities, _GlobalPlannerCapabilities):
    def pin_add_payload(self, request: AddPinRequest) -> dict[str, Any]:
        result = PinsModule(self.runtime.workspace, home=self.runtime.home).add(request)
        self._record_action(
            area="pin",
            action="pin.add",
            summary=f"Pinned: {result.pin.title}",
            metadata={"id": result.pin.id, "kind": result.pin.kind},
        )
        return self.runtime.scope_payload(
            self._governed_write(
                {
                    "status": "pinned",
                    "path": str(result.path),
                    "pin": _pin_dict(result.pin),
                },
                area="pin",
                action="pin.add",
                target=result.pin.id,
                source_of_truth="pins",
            )
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
            self._governed_write(
                {
                    "status": "updated",
                    "path": str(result.path),
                    "index_path": str(result.index_path),
                    "pin": _pin_dict(result.pin),
                },
                area="pin",
                action="pin.update",
                target=result.pin.id,
                source_of_truth="pins",
            )
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
        return self.runtime.scope_payload(
            self._governed_write(
                payload,
                area="pin",
                action="pin.archive",
                target=pin_id,
                source_of_truth="pins",
                confirmation_required=not confirm,
            )
        )

    def project_add_payload(self, request: AddProjectRequest) -> dict[str, Any]:
        project = ProjectsModule(self.runtime.workspace, home=self.runtime.home).add(request)
        self._record_action(
            area="project",
            action="project.add",
            summary=f"Added project: {project.alias}",
            metadata={"alias": project.alias},
        )
        return self.runtime.scope_payload(
            self._governed_write(
                {"status": "added", "project": _project_dict(project)},
                area="project",
                action="project.add",
                target=project.alias,
                source_of_truth="projects",
            )
        )

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
        return self.runtime.scope_payload(
            self._governed_write(
                payload,
                area="project",
                action="project.remove",
                target=alias,
                source_of_truth="projects",
            )
        )

    def project_roots_set_payload(self, roots: list[str]) -> dict[str, Any]:
        payload = ProjectsModule(self.runtime.workspace, home=self.runtime.home).configure_roots(
            roots
        )
        return self.runtime.scope_payload(
            self._governed_write(
                payload,
                area="project",
                action="project.roots_set",
                target="roots",
                source_of_truth="projects",
            )
        )


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
