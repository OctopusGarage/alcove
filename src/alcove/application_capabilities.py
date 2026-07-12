from __future__ import annotations

from dataclasses import asdict
from time import perf_counter
from typing import Any

from alcove.application_base import _Capability
from alcove.classify import ClassifyModule
from alcove.connector_sources import ConnectorSourceRegistry
from alcove.connectors.apple_notes import (
    AppleNotesConnector,
    AppleNotesImportRequest,
    AppleNotesLocalImportRequest,
)
from alcove.connectors.fetch import ConnectorFetchModule
from alcove.connectors.chrome_bookmarks import (
    ChromeBookmarksConnector,
    ChromeBookmarksImportRequest,
    ChromeBookmarksLocalImportRequest,
)
from alcove.connectors.github_stars import (
    GitHubStarsConnector,
    GitHubStarsImportRequest,
    GitHubStarsUrlImportRequest,
)
from alcove.doctor import DoctorModule
from alcove.exporter import ExportModule
from alcove.gardener import GardenerModule
from alcove.health import HealthModule
from alcove.inbox import InboxModule
from alcove.inbox_models import InboxNoteRequest, InboxProcessResult
from alcove.installer import InstallerModule
from alcove.knowledge import (
    AddConceptRequest,
    AddEntityRequest,
    AddQuestionRequest,
    KnowledgeModule,
    NoteSourceRequest,
    ReviseKnowledgeRequest,
)
from alcove.lifecycle import LifecycleModule
from alcove.linking import LinkSourceRequest, LinkingModule
from alcove.mounts import AddMountRequest, MountsModule
from alcove.okf_catalog import OkfCatalogModule
from alcove.search import SearchModule, SearchRequest
from alcove.taxonomy import load_taxonomy, split_domain_topic
from alcove.usage import UsageRecorder
from alcove.validate import ValidateModule


class _SearchCapabilities(_Capability):
    def search(
        self, request: SearchRequest, *, surface: str = "application"
    ) -> list[dict[str, Any]]:
        started = perf_counter()
        results = SearchModule(self.runtime.workspace, home=self.runtime.home).search(request)
        self._record_search_usage(
            request,
            surface=surface,
            result_count=len(results),
            duration_ms=int((perf_counter() - started) * 1000),
        )
        return results

    def search_payload(
        self,
        request: SearchRequest,
        *,
        surface: str = "application",
    ) -> dict[str, Any]:
        results = self.search(request, surface=surface)
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

    def _record_search_usage(
        self,
        request: SearchRequest,
        *,
        surface: str,
        result_count: int,
        duration_ms: int,
    ) -> None:
        if self.runtime.home is None:
            return
        UsageRecorder(self.runtime.home).record_search(
            surface=surface,
            query=request.query,
            result_count=result_count,
            duration_ms=duration_ms,
            filters={
                "type": request.type_filter,
                "tag": request.tag,
                "topic": request.topic,
                "platform": request.platform,
                "date_from": request.date_from,
                "date_to": request.date_to,
                "min_confidence": request.min_confidence,
                "status": request.status,
            },
        )


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
        mcp_toolset: str = "full",
    ) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        installer = InstallerModule(workspace, home=self.runtime.home, mcp_toolset=mcp_toolset)
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
        mcp_toolset: str = "lite",
        default_kb: str = "",
    ) -> dict[str, Any]:
        installer = InstallerModule(
            None,
            home=self.runtime.home,
            mcp_toolset=mcp_toolset,
            default_kb=default_kb,
        )
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

    def okf_catalog_build_payload(self) -> dict[str, Any]:
        if self.runtime.home is None:
            raise ValueError("Alcove home is required")
        return self.runtime.scope_payload(OkfCatalogModule(self.runtime.home).build())

    def health_payload(self, *, fix: bool = False, strict: bool = False) -> dict[str, Any]:
        if self.runtime.home is None and self.runtime.workspace is None:
            raise ValueError("Alcove home or workspace is required")
        report = HealthModule(home=self.runtime.home, workspace=self.runtime.workspace).check(
            fix=fix,
            strict=strict,
        )
        return self.runtime.scope_payload(report)

    def validate_payload(self, strict_quality: bool = False) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        issues = ValidateModule(workspace).validate(strict_quality=strict_quality)
        return self.payloads.scope({"issues": self.payloads.compact_path_rows(issues)})

    def gardener_payload(self, prune: bool = False) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        report = GardenerModule(workspace).gardener(prune=prune)
        return self.payloads.scope(
            {
                "issues": self.payloads.workspace_relative_path_rows(report.issues, workspace.root),
                "actions": self.payloads.workspace_relative_path_rows(
                    report.actions, workspace.root
                ),
            }
        )

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
        self._record_action(
            area="inbox",
            action="inbox.archive",
            summary=f"Archived inbox item: {name}",
            metadata={"item": name, "topic": topic},
        )
        return self._process_payload(result, validate=validate)

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
        return self._process_payload(result, validate=validate)

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
        return self.runtime.scope_payload(payload)

    def inbox_todo_payload(self, name: str, reason: str = "") -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        path = InboxModule(workspace).todo(name, reason)
        self._record_action(
            area="inbox",
            action="inbox.todo",
            summary=f"Deferred inbox item: {name}",
            metadata={"item": name},
        )
        return self.runtime.scope_payload({"status": "todo", "path": str(path)})

    def inbox_delete_payload(self, name: str, *, confirm: bool = False) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        payload = InboxModule(workspace).delete(name, confirm=confirm)
        self._record_action(
            area="inbox",
            action="inbox.delete",
            summary=f"Deleted inbox item: {name}",
            metadata={"item": name},
        )
        return self.runtime.scope_payload(payload)

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
    def _connector_payload(self, report: dict[str, Any]) -> dict[str, Any]:
        return dict(report)

    def connector_status_payload(self, connector: str = "") -> dict[str, Any]:
        report = ConnectorSourceRegistry(
            self.runtime.workspace,
            home=self.runtime.home,
        ).status(connector=connector or None)
        return self._connector_payload(report)

    def connector_refresh_payload(
        self,
        *,
        connector: str = "",
        stale_only: bool = True,
        source_id: str = "",
    ) -> dict[str, Any]:
        reports = []
        if connector in {"", "apple-notes"}:
            reports.append(
                AppleNotesConnector(
                    self.runtime.workspace,
                    home=self.runtime.home,
                ).refresh_sources(stale_only=stale_only, source_id=source_id)
            )
        if connector in {"", "github-stars"}:
            reports.append(
                GitHubStarsConnector(
                    self.runtime.workspace,
                    home=self.runtime.home,
                ).refresh_sources(stale_only=stale_only, source_id=source_id)
            )
        if connector in {"", "chrome-bookmarks"}:
            reports.append(
                ChromeBookmarksConnector(
                    self.runtime.workspace,
                    home=self.runtime.home,
                ).refresh_sources(stale_only=stale_only, source_id=source_id)
            )
        refreshed = sum(int(report.get("refreshed") or 0) for report in reports)
        skipped = sum(int(report.get("skipped") or 0) for report in reports)
        reused = sum(int(report.get("reused") or 0) for report in reports)
        errors = sum(int(report.get("errors") or 0) for report in reports)
        sources = [
            source
            for report in reports
            for source in report.get("sources", [])
            if isinstance(source, dict)
        ]
        payload = {
            "status": "refreshed",
            "refreshed": refreshed,
            "skipped": skipped,
            "reused": reused,
            "errors": errors,
            "sources": sources,
        }
        self._record_action(
            area="connector",
            action="connector.refresh",
            summary="Refreshed connector sources",
            metrics={
                "refreshed": refreshed,
                "skipped": skipped,
                "reused": reused,
                "errors": errors,
            },
            metadata={"connector": connector or "all", "source_id": source_id},
        )
        return self._connector_payload(payload)

    def mount_list_payload(self, status: str = "active") -> dict[str, Any]:
        mounts = [
            asdict(mount)
            for mount in MountsModule(self.runtime.workspace, home=self.runtime.home).list(status)
        ]
        return self.runtime.scope_payload({"count": len(mounts), "mounts": mounts})

    def mount_add_payload(self, request: AddMountRequest) -> dict[str, Any]:
        mount = MountsModule(self.runtime.workspace, home=self.runtime.home).add(request)
        self._record_action(
            area="mount",
            action="mount.add",
            summary=f"Mounted source: {mount.name}",
            metadata={"id": mount.id, "name": mount.name, "type": mount.type},
        )
        return self.runtime.scope_payload({"status": "mounted", "mount": asdict(mount)})

    def mount_scan_payload(
        self,
        mount_id: str | None = None,
        *,
        include_diagnostics: bool = False,
    ) -> dict[str, Any]:
        report = MountsModule(self.runtime.workspace, home=self.runtime.home).scan(
            mount_id,
            include_diagnostics=include_diagnostics,
        )
        self._record_action(
            area="mount",
            action="mount.scan",
            summary="Scanned mounted sources",
            metrics={
                "items": int(report.get("scanned") or 0),
                "skipped": int(report.get("skipped") or 0),
                "reused": int(report.get("reused") or 0),
                "mounts": 1 if isinstance(report.get("mount"), dict) else 0,
            },
            metadata={"mount_id": mount_id or ""},
        )
        return self.payloads.scope(self.payloads.mount_scan_report(report))

    def apple_notes_index_payload(self, request: AppleNotesImportRequest) -> dict[str, Any]:
        report = AppleNotesConnector(
            self.runtime.workspace,
            home=self.runtime.home,
        ).import_export(request)
        self._record_connector_index("apple_notes", report)
        return self._connector_payload(report)

    def apple_notes_import_local_payload(
        self, request: AppleNotesLocalImportRequest
    ) -> dict[str, Any]:
        report = AppleNotesConnector(
            self.runtime.workspace,
            home=self.runtime.home,
        ).import_local(request)
        self._record_connector_index("apple_notes", report)
        return self._connector_payload(report)

    def github_stars_index_payload(self, request: GitHubStarsImportRequest) -> dict[str, Any]:
        report = GitHubStarsConnector(
            self.runtime.workspace,
            home=self.runtime.home,
        ).import_export(request)
        self._record_connector_index("github_stars", report)
        return self._connector_payload(report)

    def github_stars_import_url_payload(
        self, request: GitHubStarsUrlImportRequest
    ) -> dict[str, Any]:
        report = GitHubStarsConnector(
            self.runtime.workspace,
            home=self.runtime.home,
        ).import_url(request)
        self._record_connector_index("github_stars", report)
        return self._connector_payload(report)

    def chrome_bookmarks_index_payload(
        self, request: ChromeBookmarksImportRequest
    ) -> dict[str, Any]:
        report = ChromeBookmarksConnector(
            self.runtime.workspace,
            home=self.runtime.home,
        ).import_export(request)
        self._record_connector_index("chrome_bookmarks", report)
        return self._connector_payload(report)

    def chrome_bookmarks_import_local_payload(
        self, request: ChromeBookmarksLocalImportRequest
    ) -> dict[str, Any]:
        report = ChromeBookmarksConnector(
            self.runtime.workspace,
            home=self.runtime.home,
        ).import_local(request)
        self._record_connector_index("chrome_bookmarks", report)
        return self._connector_payload(report)

    def connector_fetch_payload(self, item_path: str) -> dict[str, Any]:
        return self._connector_payload(
            ConnectorFetchModule(self.runtime.workspace, home=self.runtime.home).fetch(item_path)
        )

    def link_source_payload(self, request: LinkSourceRequest) -> dict[str, Any]:
        payload = LinkingModule(
            self.runtime.require_workspace(),
            home=self.runtime.home,
        ).link_source(request)
        self._record_action(
            area="knowledge",
            action="knowledge.link_source",
            summary=f"Linked source into KB: {request.item_path}",
            metadata={"item_path": request.item_path, "topic": request.topic},
        )
        return payload

    def _record_connector_index(self, connector: str, report: dict[str, Any]) -> None:
        scanned = int(report.get("scanned") or report.get("count") or 0)
        added = int(report.get("added") or 0)
        updated = int(report.get("updated") or 0)
        removed = int(report.get("removed") or 0)
        self._record_action(
            area="connector",
            action=f"connector.{connector}.index",
            summary=f"Indexed connector: {connector.replace('_', '-')}",
            metrics={
                "scanned": scanned,
                "added": added,
                "updated": updated,
                "removed": removed,
            },
            metadata={"connector": connector.replace("_", "-")},
        )


class _ManagedKnowledgeCapabilities(_Capability):
    def note_source_payload(self, request: NoteSourceRequest) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        result = KnowledgeModule(workspace).note_source(request)
        self._record_action(
            area="knowledge",
            action="knowledge.note_source",
            summary=f"Noted source: {request.title}",
            metadata={"title": request.title, "topic": request.topic, "platform": request.platform},
        )
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
        self._record_action(
            area="knowledge",
            action="knowledge.add_concept",
            summary=f"Added concept: {request.title}",
            metadata={"title": request.title, "topic": request.topic},
        )
        return self.runtime.scope_payload({"status": "noted", "okf_concept": str(result.path)})

    def knowledge_revise_payload(self, request: ReviseKnowledgeRequest) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        module = KnowledgeModule(workspace)
        result = module.revise(request)
        doc = module.repository.read_doc(result.path)
        title = str(
            doc.frontmatter.get("title") or doc.frontmatter.get("question") or result.path.stem
        )
        self._record_action(
            area="knowledge",
            action="knowledge.revise",
            summary=f"Revised knowledge: {title}",
            metadata={"path": request.path, "title": title},
        )
        return self.runtime.scope_payload({"status": "revised", "path": str(result.path)})

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
        self._record_action(
            area="knowledge",
            action="knowledge.delete",
            summary=f"Deleted knowledge: {title}" if confirm else f"Preview delete: {title}",
            metadata={"path": path, "title": title, "confirmed": str(confirm)},
        )
        return self.runtime.scope_payload(payload)

    def knowledge_add_question_payload(self, request: AddQuestionRequest) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        result = KnowledgeModule(workspace).add_question(request)
        self._record_action(
            area="knowledge",
            action="knowledge.add_question",
            summary=f"Added question: {request.question}",
            metadata={"question": request.question, "topic": request.topic},
        )
        return self.runtime.scope_payload({"status": "added", "okf_question": str(result.path)})

    def knowledge_add_entity_payload(self, request: AddEntityRequest) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        result = KnowledgeModule(workspace).add_entity(request)
        self._record_action(
            area="knowledge",
            action="knowledge.add_entity",
            summary=f"Added entity: {request.name}",
            metadata={"name": request.name, "topic": request.topic, "kind": request.kind},
        )
        return self.runtime.scope_payload({"status": "added", "okf_entity": str(result.path)})

    def knowledge_promote_payload(
        self, source: str, topic: str = "", summary: str = ""
    ) -> dict[str, Any]:
        workspace = self.runtime.require_workspace()
        result = KnowledgeModule(workspace).promote_source(source, topic=topic, summary=summary)
        self._record_action(
            area="knowledge",
            action="knowledge.promote",
            summary=f"Promoted source: {source}",
            metadata={"source": source, "topic": topic},
        )
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
        self._record_action(
            area="knowledge",
            action="knowledge.refresh",
            summary=f"Refreshed topic: {topic}",
            metadata={"topic": topic, "in_place": str(in_place)},
        )
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
