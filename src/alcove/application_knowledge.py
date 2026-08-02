from __future__ import annotations

from typing import Any

from alcove.application_base import _Capability
from alcove.application_search import _SearchCapabilities
from alcove.classify import ClassifyModule
from alcove.knowledge import (
    AddConceptRequest,
    AddEntityRequest,
    AddQuestionRequest,
    KnowledgeModule,
    NoteSourceRequest,
    ReviseKnowledgeRequest,
)
from alcove.lifecycle import LifecycleModule
from alcove.search import SearchRequest
from alcove.taxonomy import load_taxonomy, split_domain_topic


class _ManagedKnowledgeCapabilities(_Capability):
    def note_source_payload(self, request: NoteSourceRequest) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        result = KnowledgeModule(workspace).note_source(request)
        return self._knowledge_write_payload(
            {
                "status": "noted",
                "source_path": str(result.source_path),
                "concept_path": str(result.concept_path) if result.concept_path else "",
            },
            action="knowledge.note_source",
            summary=f"Noted source: {request.title}",
            metadata={"title": request.title, "topic": request.topic, "platform": request.platform},
            target=request.title,
        )

    def knowledge_add_concept_payload(self, request: AddConceptRequest) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        result = KnowledgeModule(workspace).add_concept(request)
        return self._knowledge_write_payload(
            {"status": "noted", "okf_concept": str(result.path)},
            action="knowledge.add_concept",
            summary=f"Added concept: {request.title}",
            metadata={"title": request.title, "topic": request.topic},
            target=request.title,
        )

    def knowledge_revise_payload(self, request: ReviseKnowledgeRequest) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        module = KnowledgeModule(workspace)
        result = module.revise(request)
        doc = module.repository.read_doc(result.path)
        title = str(
            doc.frontmatter.get("title") or doc.frontmatter.get("question") or result.path.stem
        )
        return self._knowledge_write_payload(
            {"status": "revised", "path": str(result.path)},
            action="knowledge.revise",
            summary=f"Revised knowledge: {title}",
            metadata={"path": request.path, "title": title},
            target=request.path,
        )

    def knowledge_delete_payload(
        self,
        path: str,
        *,
        confirm: bool = False,
        reason: str = "",
    ) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        payload = KnowledgeModule(workspace).delete(path, confirm=confirm, reason=reason)
        title = str(payload.get("title") or path)
        return self._knowledge_write_payload(
            payload,
            action="knowledge.delete",
            summary=f"Deleted knowledge: {title}" if confirm else f"Preview delete: {title}",
            metadata={"path": path, "title": title, "confirmed": str(confirm)},
            target=path,
            confirmation_required=not confirm,
        )

    def knowledge_add_question_payload(self, request: AddQuestionRequest) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        result = KnowledgeModule(workspace).add_question(request)
        return self._knowledge_write_payload(
            {"status": "added", "okf_question": str(result.path)},
            action="knowledge.add_question",
            summary=f"Added question: {request.question}",
            metadata={"question": request.question, "topic": request.topic},
            target=request.question,
        )

    def knowledge_add_entity_payload(self, request: AddEntityRequest) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        result = KnowledgeModule(workspace).add_entity(request)
        return self._knowledge_write_payload(
            {"status": "added", "okf_entity": str(result.path)},
            action="knowledge.add_entity",
            summary=f"Added entity: {request.name}",
            metadata={"name": request.name, "topic": request.topic, "kind": request.kind},
            target=request.name,
        )

    def knowledge_promote_payload(
        self, source: str, topic: str = "", summary: str = ""
    ) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        result = KnowledgeModule(workspace).promote_source(source, topic=topic, summary=summary)
        return self._knowledge_write_payload(
            {"status": "promoted", "okf_concept": str(result.path)},
            action="knowledge.promote",
            summary=f"Promoted source: {source}",
            metadata={"source": source, "topic": topic},
            target=source,
        )

    def knowledge_refresh_payload(
        self,
        topic: str,
        *,
        in_place: bool = False,
        summary: str = "",
    ) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        result = LifecycleModule(workspace).refresh_topic(topic, in_place=in_place, summary=summary)
        self._record_action(
            area="knowledge",
            action="knowledge.refresh",
            summary=f"Refreshed topic: {topic}",
            metadata={"topic": topic, "in_place": str(in_place)},
        )
        return self.runtime.scope_payload(
            self._governed_write(
                result,
                area="knowledge",
                action="knowledge.refresh",
                target=topic or "all",
                source_of_truth="managed-kb indexes",
            )
        )

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

    def _knowledge_write_payload(
        self,
        payload: dict[str, Any],
        *,
        action: str,
        summary: str,
        metadata: dict[str, Any],
        target: str,
        source_of_truth: str = "managed-kb knowledge",
        confirmation_required: bool = False,
    ) -> dict[str, Any]:
        self._record_action(
            area="knowledge",
            action=action,
            summary=summary,
            metadata=metadata,
        )
        return self.runtime.scope_payload(
            self._governed_write(
                payload,
                area="knowledge",
                action=action,
                target=target,
                source_of_truth=source_of_truth,
                confirmation_required=confirmation_required,
            )
        )
