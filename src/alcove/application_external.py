from __future__ import annotations

from dataclasses import asdict
from typing import Any

from alcove.application_base import _Capability
from alcove.connector_sources import ConnectorSourceRegistry
from alcove.connectors.apple_notes import (
    AppleNotesConnector,
    AppleNotesImportRequest,
    AppleNotesLocalImportRequest,
)
from alcove.connectors.chrome_bookmarks import (
    ChromeBookmarksConnector,
    ChromeBookmarksImportRequest,
    ChromeBookmarksLocalImportRequest,
)
from alcove.connectors.fetch import ConnectorFetchModule
from alcove.connectors.github_stars import (
    GitHubStarsConnector,
    GitHubStarsImportRequest,
    GitHubStarsUrlImportRequest,
)
from alcove.linking import LinkSourceRequest, LinkingModule
from alcove.mounts import AddMountRequest, MountIndexPolicy, MountsModule


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
        return self._connector_payload(
            self._governed_write(
                payload,
                area="connector",
                action="connector.refresh",
                target=connector or "all",
                source_of_truth="connector indexes",
            )
        )

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
        return self.runtime.scope_payload(
            self._governed_write(
                {"status": "mounted", "mount": asdict(mount)},
                area="mount",
                action="mount.add",
                target=mount.id,
                source_of_truth="mount registry",
            )
        )

    def mount_update_policy_payload(
        self,
        mount_id: str,
        policy: MountIndexPolicy,
    ) -> dict[str, Any]:
        mount = MountsModule(self.runtime.workspace, home=self.runtime.home).update_policy(
            mount_id, policy
        )
        self._record_action(
            area="mount",
            action="mount.update_policy",
            summary=f"Updated mount index policy: {mount.name}",
            metadata={"id": mount.id, "name": mount.name, "profile": mount.index_policy.profile},
        )
        mount_record = asdict(mount)
        mount_record["index_policy"] = mount.index_policy.as_config()
        return self.runtime.scope_payload(
            self._governed_write(
                {"status": "updated", "mount": mount_record},
                area="mount",
                action="mount.update_policy",
                target=mount.id,
                source_of_truth="mount registry",
            )
        )

    def mount_scan_payload(
        self,
        mount_id: str | None = None,
        *,
        include_diagnostics: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        report = MountsModule(self.runtime.workspace, home=self.runtime.home).scan(
            mount_id,
            include_diagnostics=include_diagnostics,
            dry_run=dry_run,
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
        return self.payloads.scope(
            self._governed_write(
                self.payloads.mount_scan_report(report),
                area="mount",
                action="mount.scan",
                target=mount_id or "all",
                source_of_truth="mount indexes",
            )
        )

    def apple_notes_index_payload(self, request: AppleNotesImportRequest) -> dict[str, Any]:
        report = AppleNotesConnector(
            self.runtime.workspace,
            home=self.runtime.home,
        ).import_export(request)
        self._record_connector_index("apple_notes", report)
        return self._connector_payload(
            self._governed_write(
                report,
                area="connector",
                action="connector.apple_notes.index",
                target=request.export_dir,
                source_of_truth="connector indexes",
            )
        )

    def apple_notes_import_local_payload(
        self, request: AppleNotesLocalImportRequest
    ) -> dict[str, Any]:
        report = AppleNotesConnector(
            self.runtime.workspace,
            home=self.runtime.home,
        ).import_local(request)
        self._record_connector_index("apple_notes", report)
        return self._connector_payload(
            self._governed_write(
                report,
                area="connector",
                action="connector.apple_notes.import_local",
                target=request.source_id,
                source_of_truth="connector indexes",
            )
        )

    def github_stars_index_payload(self, request: GitHubStarsImportRequest) -> dict[str, Any]:
        report = GitHubStarsConnector(
            self.runtime.workspace,
            home=self.runtime.home,
        ).import_export(request)
        self._record_connector_index("github_stars", report)
        return self._connector_payload(
            self._governed_write(
                report,
                area="connector",
                action="connector.github_stars.index",
                target=request.source_id,
                source_of_truth="connector indexes",
            )
        )

    def github_stars_import_url_payload(
        self, request: GitHubStarsUrlImportRequest
    ) -> dict[str, Any]:
        report = GitHubStarsConnector(
            self.runtime.workspace,
            home=self.runtime.home,
        ).import_url(request)
        self._record_connector_index("github_stars", report)
        return self._connector_payload(
            self._governed_write(
                report,
                area="connector",
                action="connector.github_stars.import_url",
                target=request.source,
                source_of_truth="connector indexes",
            )
        )

    def chrome_bookmarks_index_payload(
        self, request: ChromeBookmarksImportRequest
    ) -> dict[str, Any]:
        report = ChromeBookmarksConnector(
            self.runtime.workspace,
            home=self.runtime.home,
        ).import_export(request)
        self._record_connector_index("chrome_bookmarks", report)
        return self._connector_payload(
            self._governed_write(
                report,
                area="connector",
                action="connector.chrome_bookmarks.index",
                target=request.source_id,
                source_of_truth="connector indexes",
            )
        )

    def chrome_bookmarks_import_local_payload(
        self, request: ChromeBookmarksLocalImportRequest
    ) -> dict[str, Any]:
        report = ChromeBookmarksConnector(
            self.runtime.workspace,
            home=self.runtime.home,
        ).import_local(request)
        self._record_connector_index("chrome_bookmarks", report)
        return self._connector_payload(
            self._governed_write(
                report,
                area="connector",
                action="connector.chrome_bookmarks.import_local",
                target=request.source_id,
                source_of_truth="connector indexes",
            )
        )

    def connector_fetch_payload(self, item_path: str) -> dict[str, Any]:
        return self._connector_payload(
            ConnectorFetchModule(self.runtime.workspace, home=self.runtime.home).fetch(item_path)
        )

    def link_source_payload(self, request: LinkSourceRequest) -> dict[str, Any]:
        payload = LinkingModule(
            self.runtime.require_workspace(),
            home=self.runtime.home,
        ).link_source(request)
        title = _linked_source_title(payload, fallback=request.item_path)
        self._record_action(
            area="knowledge",
            action="knowledge.link_source",
            summary=f"Linked source into KB: {title}",
            metadata={"item_path": request.item_path, "topic": request.topic, "title": title},
        )
        return self._governed_write(
            payload,
            area="knowledge",
            action="knowledge.link_source",
            target=request.item_path,
            source_of_truth="managed-kb knowledge",
        )

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


def _linked_source_title(payload: dict[str, Any], *, fallback: str) -> str:
    source = payload.get("source")
    if isinstance(source, dict):
        title = str(source.get("title") or "").strip()
        if title:
            return title
    return fallback
