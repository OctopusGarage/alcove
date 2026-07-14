from __future__ import annotations

from pathlib import Path

from alcove.connectors.apple_notes import AppleNotesConnector
from alcove.connectors.chrome_bookmarks import ChromeBookmarksConnector
from alcove.connectors.github_stars import GitHubStarsConnector
from alcove.dashboard import DashboardModule
from alcove.home import AlcoveHome
from alcove.markdown import MarkdownDoc, MarkdownRepository
from alcove.mounts import MountsModule
from alcove.okf import okf_schema_for
from alcove.okf_catalog import OkfCatalogModule
from alcove.paths import compact_user_path
from alcove.pins import PinsModule
from alcove.prompts import PromptsModule
from alcove.usage import UsageRecorder
from alcove.workspace import Workspace


class HealthRepairModule:
    """Repair and rebuild operations used by the Health module."""

    def __init__(
        self,
        *,
        home: AlcoveHome | None,
        workspace: Workspace | None,
        repo: MarkdownRepository,
    ) -> None:
        self.home = home
        self.workspace = workspace
        self.repo = repo

    def safe_rebuilds(
        self,
        *,
        deep: bool = False,
        refresh_stale_connectors: bool = False,
        refresh_all_connectors: bool = False,
    ) -> list[dict[str, str]]:
        actions: list[dict[str, str]] = []
        repaired_workspaces: set[Path] = set()
        if self.workspace is not None:
            actions.extend(self._repair_workspace_okf_schemas(self.workspace))
            repaired_workspaces.add(self.workspace.root.resolve())
        if self.home is not None:
            actions.extend(self._repair_registered_kbs(repaired_workspaces))
            actions.extend(self._rebuild_home_indexes())
            if refresh_stale_connectors or refresh_all_connectors:
                actions.append(self._refresh_connectors(stale_only=not refresh_all_connectors))
            if deep:
                actions.extend(self._deep_rebuilds())
        return actions

    def _repair_registered_kbs(self, repaired_workspaces: set[Path]) -> list[dict[str, str]]:
        if self.home is None:
            return []
        actions: list[dict[str, str]] = []
        for record in self.home.list_knowledge_bases():
            if not record.path.exists():
                continue
            root = record.path.resolve()
            if root in repaired_workspaces:
                continue
            try:
                actions.extend(self._repair_workspace_okf_schemas(Workspace.discover(record.path)))
                repaired_workspaces.add(root)
            except Exception as exc:
                actions.append(
                    {
                        "module": "managed_kb",
                        "action": "schema_repair_skipped",
                        "path": compact_user_path(record.path),
                        "reason": str(exc),
                    }
                )
        return actions

    def _rebuild_home_indexes(self) -> list[dict[str, str]]:
        if self.home is None:
            return []
        pin_index = PinsModule(home=self.home).rebuild_index()
        prompt_index = PromptsModule(home=self.home).rebuild_index()
        catalog = OkfCatalogModule(self.home).build()
        return [
            {
                "module": "pins",
                "action": "rebuilt",
                "path": compact_user_path(pin_index),
            },
            {
                "module": "prompts",
                "action": "rebuilt",
                "path": compact_user_path(prompt_index),
            },
            {
                "module": "okf_catalog",
                "action": "rebuilt",
                "path": compact_user_path(str(catalog["root"])),
            },
        ]

    def _deep_rebuilds(self) -> list[dict[str, str]]:
        if self.home is None:
            return []
        mount_report = MountsModule(home=self.home).scan()
        usage_report = UsageRecorder(self.home).write_rollups()
        dashboard_report = DashboardModule(self.home).build(build_frontend=False)
        catalog = OkfCatalogModule(self.home).build()
        return [
            {
                "module": "mounts",
                "action": "scanned",
                "path": compact_user_path(self.home.paths().mounts),
                "scanned": str(int(mount_report.get("scanned") or 0)),
                "skipped": str(int(mount_report.get("skipped") or 0)),
                "reused": str(int(mount_report.get("reused") or 0)),
            },
            {
                "module": "usage",
                "action": "rolled_up",
                "path": compact_user_path(self.home.paths().stats),
                "events": str(int(usage_report.get("total_events") or 0)),
            },
            {
                "module": "dashboard",
                "action": "rebuilt",
                "path": compact_user_path(str(dashboard_report.get("snapshot") or "")),
            },
            {
                "module": "okf_catalog",
                "action": "rebuilt",
                "path": compact_user_path(str(catalog["root"])),
            },
        ]

    def _refresh_connectors(self, *, stale_only: bool) -> dict[str, str]:
        reports = [
            AppleNotesConnector(self.workspace, home=self.home).refresh_sources(
                stale_only=stale_only
            ),
            GitHubStarsConnector(self.workspace, home=self.home).refresh_sources(
                stale_only=stale_only
            ),
            ChromeBookmarksConnector(self.workspace, home=self.home).refresh_sources(
                stale_only=stale_only
            ),
        ]
        return {
            "module": "connectors",
            "action": "refreshed_stale" if stale_only else "refreshed_all",
            "path": compact_user_path(self.home.paths().connectors) if self.home else "",
            "refreshed": str(sum(int(report.get("refreshed") or 0) for report in reports)),
            "skipped": str(sum(int(report.get("skipped") or 0) for report in reports)),
            "reused": str(sum(int(report.get("reused") or 0) for report in reports)),
            "errors": str(sum(int(report.get("errors") or 0) for report in reports)),
        }

    def _repair_workspace_okf_schemas(self, workspace: Workspace) -> list[dict[str, str]]:
        repaired = 0
        knowledge_root = workspace.paths().knowledge
        if not knowledge_root.exists():
            return []
        for path in sorted(knowledge_root.rglob("*.md"), key=lambda item: item.as_posix()):
            if path.name in {"index.md", "log.md"}:
                continue
            try:
                doc = self.repo.read_doc(path)
            except OSError:
                continue
            doc_type = str(doc.frontmatter.get("type") or "")
            expected_schema = okf_schema_for(doc_type)
            if not expected_schema or str(doc.frontmatter.get("schema") or ""):
                continue
            self.repo.write_doc(
                path,
                MarkdownDoc(
                    frontmatter={**doc.frontmatter, "schema": expected_schema},
                    body=doc.body,
                ),
            )
            repaired += 1
        if not repaired:
            return []
        return [
            {
                "module": "managed_kb",
                "action": "repaired_missing_okf_schema",
                "path": compact_user_path(workspace.root),
                "count": str(repaired),
            }
        ]
