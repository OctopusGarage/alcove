from __future__ import annotations

from dataclasses import asdict
from typing import Any

from alcove.application_base import _Capability
from alcove.application_system import _SystemCapabilities
from alcove.classify import ClassifyModule
from alcove.inbox import InboxModule
from alcove.inbox_models import InboxNoteRequest, InboxProcessResult


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
        self._record_action(
            area="inbox",
            action="inbox.archive",
            summary=f"Archived inbox item: {name}",
            metadata={"item": name, "topic": topic},
        )
        return self._process_payload(
            result,
            validate=validate,
            area="inbox",
            action="inbox.archive",
            target=name,
        )

    def inbox_note_payload(
        self, request: InboxNoteRequest, *, validate: bool = False
    ) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        result = InboxModule(workspace).note(request)
        self._record_action(
            area="inbox",
            action="inbox.note",
            summary=f"Noted inbox item: {request.name}",
            metadata={"item": request.name, "topic": request.topic},
        )
        return self._process_payload(
            result,
            validate=validate,
            area="inbox",
            action="inbox.note",
            target=request.name,
        )

    def inbox_manual_add_payload(
        self, title: str, content: str, source: str = ""
    ) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        payload = InboxModule(workspace).add_manual(title=title, content=content, source=source)
        self._record_action(
            area="inbox",
            action="inbox.manual_add",
            summary=f"Added manual inbox item: {title}",
            metadata={"title": title, "source": source},
        )
        return self.runtime.scope_payload(
            self._governed_write(
                payload,
                area="inbox",
                action="inbox.manual_add",
                target=title,
                source_of_truth="managed-kb inbox",
            )
        )

    def inbox_todo_payload(self, name: str, reason: str = "") -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        path = InboxModule(workspace).todo(name, reason)
        self._record_action(
            area="inbox",
            action="inbox.todo",
            summary=f"Deferred inbox item: {name}",
            metadata={"item": name},
        )
        return self.runtime.scope_payload(
            self._governed_write(
                {"status": "todo", "path": str(path)},
                area="inbox",
                action="inbox.todo",
                target=name,
                source_of_truth="managed-kb todo",
            )
        )

    def inbox_delete_payload(self, name: str, *, confirm: bool = False) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        payload = InboxModule(workspace).delete(name, confirm=confirm)
        self._record_action(
            area="inbox",
            action="inbox.delete",
            summary=f"Deleted inbox item: {name}",
            metadata={"item": name},
        )
        return self.runtime.scope_payload(
            self._governed_write(
                payload,
                area="inbox",
                action="inbox.delete",
                target=name,
                source_of_truth="managed-kb inbox",
                confirmation_required=not confirm,
            )
        )

    def _process_payload(
        self,
        result: InboxProcessResult,
        *,
        validate: bool = False,
        area: str,
        action: str,
        target: str,
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
        return self.runtime.scope_payload(
            self._governed_write(
                payload,
                area=area,
                action=action,
                target=target,
                source_of_truth="managed-kb knowledge",
            )
        )
