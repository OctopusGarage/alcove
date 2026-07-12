from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

import yaml

from alcove.automations import AutomationsModule
from alcove.blog_monitor import BlogMonitorModule
from alcove.connector_sources import ConnectorSourceRegistry
from alcove.connectors.apple_notes import AppleNotesConnector
from alcove.connectors.chrome_bookmarks import ChromeBookmarksConnector
from alcove.connectors.github_stars import GitHubStarsConnector
from alcove.dashboard import DASHBOARD_SNAPSHOT_VERSION, DashboardModule
from alcove.home import AlcoveHome
from alcove.markdown import MarkdownDoc, MarkdownRepository
from alcove.mounts import MountsModule
from alcove.okf import okf_schema_for
from alcove.okf_catalog import CATALOG_FILES, OkfCatalogModule
from alcove.paths import compact_user_path
from alcove.pins import PIN_REQUIRED_FIELDS, PIN_SCHEMA, PinsModule
from alcove.prompts import PROMPT_REQUIRED_FIELDS, PROMPT_SCHEMA, PromptsModule
from alcove.publishers import PublisherModule
from alcove.radars import RadarModule
from alcove.usage import UsageRecorder
from alcove.validate import ValidateModule
from alcove.watchers import WatcherModule
from alcove.workspace import Workspace


@dataclass(frozen=True)
class HealthIssue:
    severity: str
    module: str
    kind: str
    path: str
    message: str
    remediation: str = ""


class HealthModule:
    """Cross-module data and derived-index health checks."""

    def __init__(
        self,
        *,
        home: AlcoveHome | None = None,
        workspace: Workspace | None = None,
        repo: MarkdownRepository | None = None,
    ) -> None:
        self.home = home
        self.workspace = workspace
        self.repo = repo or MarkdownRepository()

    def check(
        self,
        *,
        fix: bool = False,
        strict: bool = False,
        deep: bool = False,
        refresh_stale_connectors: bool = False,
        refresh_all_connectors: bool = False,
    ) -> dict[str, Any]:
        actions: list[dict[str, Any]] = []
        if fix:
            actions.extend(
                self._safe_rebuilds(
                    deep=deep,
                    refresh_stale_connectors=refresh_stale_connectors,
                    refresh_all_connectors=refresh_all_connectors,
                )
            )

        issues: list[HealthIssue] = []
        counts: dict[str, int] = {}
        if self.workspace is not None:
            self._check_workspace(self.workspace, issues, counts, strict=strict)
        if self.home is not None:
            self._check_home(self.home, issues, counts, strict=strict)
        issues = self._dedupe_issues(issues)

        return {
            "status": self._status(issues),
            "home": compact_user_path(self.home.root) if self.home is not None else "",
            "workspace": compact_user_path(self.workspace.root)
            if self.workspace is not None
            else "",
            "counts": counts,
            "issues": [asdict(issue) for issue in issues],
            "actions": actions,
        }

    def _safe_rebuilds(
        self,
        *,
        deep: bool = False,
        refresh_stale_connectors: bool = False,
        refresh_all_connectors: bool = False,
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        repaired_workspaces: set[Path] = set()
        if self.workspace is not None:
            actions.extend(self._repair_workspace_okf_schemas(self.workspace))
            repaired_workspaces.add(self.workspace.root.resolve())
        if self.home is not None:
            for record in self.home.list_knowledge_bases():
                if not record.path.exists():
                    continue
                root = record.path.resolve()
                if root in repaired_workspaces:
                    continue
                try:
                    actions.extend(
                        self._repair_workspace_okf_schemas(Workspace.discover(record.path))
                    )
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
            pin_index = PinsModule(home=self.home).rebuild_index()
            actions.append(
                {
                    "module": "pins",
                    "action": "rebuilt",
                    "path": compact_user_path(pin_index),
                }
            )
            prompt_index = PromptsModule(home=self.home).rebuild_index()
            actions.append(
                {
                    "module": "prompts",
                    "action": "rebuilt",
                    "path": compact_user_path(prompt_index),
                }
            )
            catalog = OkfCatalogModule(self.home).build()
            actions.append(
                {
                    "module": "okf_catalog",
                    "action": "rebuilt",
                    "path": compact_user_path(str(catalog["root"])),
                }
            )
            if refresh_stale_connectors or refresh_all_connectors:
                actions.append(self._refresh_connectors(stale_only=not refresh_all_connectors))
            if deep:
                mount_report = MountsModule(home=self.home).scan()
                actions.append(
                    {
                        "module": "mounts",
                        "action": "scanned",
                        "path": compact_user_path(self.home.paths().mounts),
                        "scanned": str(int(mount_report.get("scanned") or 0)),
                        "skipped": str(int(mount_report.get("skipped") or 0)),
                        "reused": str(int(mount_report.get("reused") or 0)),
                    }
                )
                usage_report = UsageRecorder(self.home).write_rollups()
                actions.append(
                    {
                        "module": "usage",
                        "action": "rolled_up",
                        "path": compact_user_path(self.home.paths().stats),
                        "events": str(int(usage_report.get("total_events") or 0)),
                    }
                )
                dashboard_report = DashboardModule(self.home).build(build_frontend=False)
                actions.append(
                    {
                        "module": "dashboard",
                        "action": "rebuilt",
                        "path": compact_user_path(str(dashboard_report.get("snapshot") or "")),
                    }
                )
                catalog = OkfCatalogModule(self.home).build()
                actions.append(
                    {
                        "module": "okf_catalog",
                        "action": "rebuilt",
                        "path": compact_user_path(str(catalog["root"])),
                    }
                )
        return actions

    def _refresh_connectors(self, *, stale_only: bool) -> dict[str, Any]:
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

    def _check_workspace(
        self,
        workspace: Workspace,
        issues: list[HealthIssue],
        counts: dict[str, int],
        *,
        strict: bool,
    ) -> None:
        paths = workspace.paths()
        for name in ("knowledge", "inbox", "archive", "todo"):
            path = getattr(paths, name)
            if not path.exists():
                self._issue(
                    issues,
                    "error",
                    "managed_kb",
                    "missing_path",
                    path,
                    f"Managed KB path is missing: {name}",
                    "Run `alcove init` or repair .alcove/config.yml paths.",
                )
        validation_issues = ValidateModule(workspace).validate(strict_quality=strict)
        counts["managed_kb_validation_issues"] = len(validation_issues)
        for issue in validation_issues:
            self._issue(
                issues,
                "error",
                "managed_kb",
                str(issue.get("kind") or "validation_issue"),
                str(issue.get("path") or ""),
                str(issue.get("message") or "Managed KB validation issue"),
                "Run `alcove validate --strict-quality --json` for details.",
            )
        self._check_markdown_okf(
            paths.knowledge,
            module="managed_kb",
            issues=issues,
            counts=counts,
            allowed_loose_types={"Domain", "Topic", "Tag"},
        )

    def _check_home(
        self,
        home: AlcoveHome,
        issues: list[HealthIssue],
        counts: dict[str, int],
        *,
        strict: bool,
    ) -> None:
        paths = home.paths()
        for name in (
            "pins",
            "prompts",
            "tasks",
            "projects",
            "mounts",
            "connectors",
            "knowledge_bases",
        ):
            path = getattr(paths, name)
            if not path.exists():
                self._issue(
                    issues,
                    "error",
                    name,
                    "missing_path",
                    path,
                    f"Alcove Home module path is missing: {name}",
                    "Run `alcove home init`.",
                )
        self._check_registered_kbs(home, issues, counts, strict=strict)
        self._check_pins(paths.pins, issues, counts)
        self._check_prompts(paths.prompts, issues, counts)
        self._check_json_store(paths.tasks / "tasks.json", "tasks", issues, counts)
        self._check_json_store(paths.projects / "projects.json", "projects", issues, counts)
        self._check_mounts(paths.mounts, issues, counts)
        self._check_connectors(paths.connectors, issues, counts)
        self._check_connector_sources(home, issues, counts)
        self._check_catalog(paths.okf, issues, counts)
        self._check_dashboard(home, issues, counts)
        self._check_publishers(home, issues, counts)
        self._check_radars(home, issues, counts)
        self._check_watchers(home, issues, counts)
        self._check_blogs(home, issues, counts)
        self._check_automations(home, issues, counts)
        self._check_usage_stats(home, issues, counts)

    def _check_registered_kbs(
        self,
        home: AlcoveHome,
        issues: list[HealthIssue],
        counts: dict[str, int],
        *,
        strict: bool,
    ) -> None:
        records = home.list_knowledge_bases()
        counts["registered_kbs"] = len(records)
        for record in records:
            if not record.path.exists():
                self._issue(
                    issues,
                    "error",
                    "managed_kb_registry",
                    "missing_registered_kb",
                    record.config_path,
                    f"Registered managed KB path does not exist: {record.name}",
                    "Update or remove the registry file under ~/.alcove/knowledge-bases/.",
                )
                continue
            try:
                self._check_workspace(
                    Workspace.discover(record.path), issues, counts, strict=strict
                )
            except Exception as exc:
                self._issue(
                    issues,
                    "error",
                    "managed_kb_registry",
                    "invalid_registered_kb",
                    record.path,
                    f"Registered KB cannot be opened: {exc}",
                    "Run `alcove kb install <name> --status --json` and repair the KB config.",
                )

    def _check_pins(
        self,
        root: Path,
        issues: list[HealthIssue],
        counts: dict[str, int],
    ) -> None:
        docs = self._typed_docs(root, "Pin", issues, "pins")
        counts["pins"] = len(docs)
        for doc in docs:
            self._require_fields(doc, PIN_REQUIRED_FIELDS, "pins", issues)
            self._require_schema(doc, PIN_SCHEMA, "pins", issues)
        self._check_json_index_count(
            root / "index.json",
            "pins",
            "pins",
            len(docs),
            issues,
            counts,
            "Run `alcove pin rebuild-index`.",
        )
        self._check_markdown_doc(root / "index.md", "pins", issues, required_type="Pins Index")

    def _check_prompts(
        self,
        root: Path,
        issues: list[HealthIssue],
        counts: dict[str, int],
    ) -> None:
        docs = self._typed_docs(root, "Prompt", issues, "prompts")
        counts["prompts"] = len(docs)
        for doc in docs:
            self._require_fields(doc, PROMPT_REQUIRED_FIELDS, "prompts", issues)
            self._require_schema(doc, PROMPT_SCHEMA, "prompts", issues)
        self._check_json_index_count(
            root / "index.json",
            "prompts",
            "prompts",
            len(docs),
            issues,
            counts,
            "Run `alcove prompt rebuild-index`.",
        )

    def _check_mounts(
        self,
        root: Path,
        issues: list[HealthIssue],
        counts: dict[str, int],
    ) -> None:
        mounts = self._json_list(root / "mounts.json", "mounts", issues, "mounts")
        counts["mounts"] = len(mounts)
        for mount in mounts:
            mount_id = str(mount.get("id") or "")
            if not mount_id:
                self._issue(
                    issues,
                    "error",
                    "mounts",
                    "missing_mount_id",
                    root / "mounts.json",
                    "Mount record is missing id.",
                    "Remove or repair the mount record.",
                )
                continue
            if str(mount.get("status") or "active") == "active":
                source = Path(str(mount.get("path") or "")).expanduser()
                if not source.exists():
                    self._issue(
                        issues,
                        "warning",
                        "mounts",
                        "missing_mount_source",
                        source,
                        f"Active mount source does not exist: {mount_id}",
                        "Repair the mount path or archive the mount.",
                    )
            index_path = root / "indexes" / f"{mount_id}.json"
            payload = self._read_json(index_path, issues, "mounts")
            items = self._items(payload)
            counts[f"mount_items:{mount_id}"] = len(items)
            self._check_derived_okf_count(
                root / "okf" / mount_id,
                "mounts",
                len(items),
                issues,
                f"Run `alcove mount scan {mount_id}`.",
            )

    def _check_connectors(
        self,
        root: Path,
        issues: list[HealthIssue],
        counts: dict[str, int],
    ) -> None:
        if not root.exists():
            return
        connectors = 0
        for index_path in sorted(root.glob("*/index.json"), key=lambda path: path.as_posix()):
            connectors += 1
            connector_id = index_path.parent.name
            payload = self._read_json(index_path, issues, "connectors")
            items = self._items(payload)
            counts[f"connector_items:{connector_id}"] = len(items)
            if not str(payload.get("connector") or connector_id):
                self._issue(
                    issues,
                    "error",
                    "connectors",
                    "missing_connector_id",
                    index_path,
                    "Connector index is missing connector id.",
                    "Refresh or re-import the connector.",
                )
            self._check_derived_okf_count(
                index_path.parent / "okf",
                "connectors",
                len(items),
                issues,
                "Run `alcove connector refresh --connector "
                f"{connector_id} --all` or re-import the connector.",
            )
        counts["connectors"] = connectors

    def _check_connector_sources(
        self,
        home: AlcoveHome,
        issues: list[HealthIssue],
        counts: dict[str, int],
    ) -> None:
        root = home.paths().connectors
        source_paths = sorted(root.glob("*/sources/*.yml"), key=lambda path: path.as_posix())
        counts["connector_sources"] = len(source_paths)
        for path in source_paths:
            try:
                yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError) as exc:
                self._issue(
                    issues,
                    "error",
                    "connectors",
                    "invalid_yaml",
                    path,
                    f"Could not parse connector source YAML: {exc}",
                    "Repair the source registry or re-import the connector source.",
                )
        try:
            status_rows = ConnectorSourceRegistry(home=home).status().get("sources", [])
        except Exception as exc:
            self._issue(
                issues,
                "error",
                "connectors",
                "invalid_connector_sources",
                root,
                f"Connector source registry cannot be loaded: {exc}",
                "Repair connector source YAML under ~/.alcove/connectors/*/sources/.",
            )
            return
        counts["connector_source_status_rows"] = len(
            [row for row in status_rows if isinstance(row, dict)]
        )
        for row in status_rows:
            if not isinstance(row, dict):
                continue
            status = str(row.get("status") or "")
            if status not in {"stale", "error"}:
                continue
            connector = str(row.get("connector") or "")
            source_id = str(row.get("id") or "")
            self._issue(
                issues,
                "warning",
                "connectors",
                "connector_source_error" if status == "error" else "connector_source_stale",
                root / connector / "sources" / f"{source_id}.yml",
                f"Connector source {connector}/{source_id} is {status}.",
                "Run `alcove connector refresh --stale --json` or inspect the connector source.",
            )

    def _check_catalog(
        self,
        root: Path,
        issues: list[HealthIssue],
        counts: dict[str, int],
    ) -> None:
        existing = 0
        for relative in CATALOG_FILES:
            path = root / relative
            if path.is_file():
                existing += 1
                if path.name not in {"index.md", "log.md"}:
                    self._check_markdown_doc(path, "okf_catalog", issues)
            else:
                self._issue(
                    issues,
                    "warning",
                    "okf_catalog",
                    "missing_catalog_file",
                    path,
                    f"Global OKF catalog file is missing: {relative}",
                    "Run `alcove okf catalog build` or `alcove health --fix`.",
                )
        counts["okf_catalog_files"] = existing

    def _check_dashboard(
        self,
        home: AlcoveHome,
        issues: list[HealthIssue],
        counts: dict[str, int],
    ) -> None:
        path = home.root / "dashboard" / "snapshot.json"
        if not path.exists():
            counts["dashboard_snapshots"] = 0
            return
        payload = self._read_json(path, issues, "dashboard")
        counts["dashboard_snapshots"] = 1 if payload else 0
        required = {"snapshot_version", "generated_at", "summary", "modules", "usage"}
        missing = sorted(field for field in required if field not in payload)
        version = payload.get("snapshot_version")
        if missing or version != DASHBOARD_SNAPSHOT_VERSION:
            self._issue(
                issues,
                "error",
                "dashboard",
                "invalid_dashboard_snapshot",
                path,
                "Dashboard snapshot is missing required fields or has an unsupported version.",
                "Run `alcove dashboard --home <home> build` or `alcove health --fix --deep`.",
            )

    def _check_publishers(
        self,
        home: AlcoveHome,
        issues: list[HealthIssue],
        counts: dict[str, int],
    ) -> None:
        definitions_root = home.root / "publishers" / "definitions"
        counts["publisher_definitions"] = self._check_yaml_tree(
            definitions_root, "publishers", issues
        )
        runs_root = home.root / "publishers" / "runs"
        counts["publisher_runs"] = self._check_json_tree(runs_root, "publishers", issues)
        if definitions_root.exists():
            try:
                PublisherModule(home).list(status="")
            except Exception as exc:
                self._issue(
                    issues,
                    "error",
                    "publishers",
                    "invalid_publisher_definitions",
                    definitions_root,
                    f"Publisher definitions cannot be loaded: {exc}",
                    "Repair publisher definitions or re-run `alcove publish init apple-notes`.",
                )

    def _check_radars(
        self,
        home: AlcoveHome,
        issues: list[HealthIssue],
        counts: dict[str, int],
    ) -> None:
        definitions_root = home.root / "radars" / "definitions"
        counts["radar_definitions"] = self._check_yaml_tree(definitions_root, "radars", issues)
        counts["radar_runs"] = self._check_json_tree(
            home.root / "radars" / "runs", "radars", issues
        )
        if definitions_root.exists():
            try:
                RadarModule(home).list(status="")
            except Exception as exc:
                self._issue(
                    issues,
                    "error",
                    "radars",
                    "invalid_radar_definitions",
                    definitions_root,
                    f"Radar definitions cannot be loaded: {exc}",
                    "Repair radar definitions or re-run `alcove radar init`.",
                )

    def _check_watchers(
        self,
        home: AlcoveHome,
        issues: list[HealthIssue],
        counts: dict[str, int],
    ) -> None:
        root = home.root / "watchers" / "sources"
        counts["watch_sources"] = self._check_yaml_tree(root, "watchers", issues)
        if root.exists():
            try:
                WatcherModule(home).list_sources(status="")
            except Exception as exc:
                self._issue(
                    issues,
                    "error",
                    "watchers",
                    "invalid_watch_sources",
                    root,
                    f"Watcher sources cannot be loaded: {exc}",
                    "Repair watcher sources or recreate them through `alcove watch add`.",
                )

    def _check_blogs(
        self,
        home: AlcoveHome,
        issues: list[HealthIssue],
        counts: dict[str, int],
    ) -> None:
        sources_root = home.root / "blog-monitor" / "sources"
        counts["blog_sources"] = self._check_yaml_tree(sources_root, "blog_monitor", issues)
        counts["blog_runs"] = self._check_json_tree(
            home.root / "blog-monitor" / "runs", "blog_monitor", issues
        )
        if sources_root.exists():
            try:
                BlogMonitorModule(home).list_sources(status="")
            except Exception as exc:
                self._issue(
                    issues,
                    "error",
                    "blog_monitor",
                    "invalid_blog_sources",
                    sources_root,
                    f"Blog monitor sources cannot be loaded: {exc}",
                    "Repair blog sources or recreate them through `alcove blog add`.",
                )

    def _check_automations(
        self,
        home: AlcoveHome,
        issues: list[HealthIssue],
        counts: dict[str, int],
    ) -> None:
        jobs_root = home.root / "automations" / "jobs"
        counts["automation_jobs"] = self._check_yaml_tree(jobs_root, "automations", issues)
        counts["automation_runs"] = self._check_json_tree(
            home.root / "automations" / "runs", "automations", issues
        )
        if jobs_root.exists():
            try:
                AutomationsModule(home).list_jobs(status="")
            except Exception as exc:
                self._issue(
                    issues,
                    "error",
                    "automations",
                    "invalid_automation_jobs",
                    jobs_root,
                    f"Automation jobs cannot be loaded: {exc}",
                    "Repair automation jobs or recreate them through `alcove automation add-*`.",
                )

    def _check_usage_stats(
        self,
        home: AlcoveHome,
        issues: list[HealthIssue],
        counts: dict[str, int],
    ) -> None:
        summary_path = home.paths().stats / "summary.json"
        if summary_path.exists():
            self._read_json(summary_path, issues, "usage")
            counts["usage_summary_files"] = 1
        else:
            counts["usage_summary_files"] = 0
        counts["usage_daily_files"] = self._check_json_tree(
            home.paths().stats / "daily", "usage", issues
        )

    def _check_yaml_tree(
        self,
        root: Path,
        module: str,
        issues: list[HealthIssue],
    ) -> int:
        if not root.exists():
            return 0
        count = 0
        for path in sorted(
            [*root.glob("*.yml"), *root.glob("*.yaml")], key=lambda item: item.as_posix()
        ):
            count += 1
            try:
                yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError) as exc:
                self._issue(
                    issues,
                    "error",
                    module,
                    "invalid_yaml",
                    path,
                    f"Could not parse YAML: {exc}",
                    "Repair or recreate the module configuration.",
                )
        return count

    def _check_json_tree(
        self,
        root: Path,
        module: str,
        issues: list[HealthIssue],
    ) -> int:
        if not root.exists():
            return 0
        count = 0
        for path in sorted(root.glob("*.json"), key=lambda item: item.as_posix()):
            count += 1
            self._read_json(path, issues, module)
        return count

    def _check_markdown_okf(
        self,
        root: Path,
        *,
        module: str,
        issues: list[HealthIssue],
        counts: dict[str, int],
        allowed_loose_types: set[str] | None = None,
    ) -> None:
        checked = 0
        for path in sorted(root.rglob("*.md"), key=lambda item: item.as_posix()):
            if path.name in {"index.md", "log.md"}:
                continue
            doc = self._read_doc(path, module, issues)
            if doc is None:
                continue
            checked += 1
            doc_type = str(doc.frontmatter.get("type") or "")
            if not doc_type:
                self._issue(
                    issues,
                    "error",
                    module,
                    "missing_okf_type",
                    path,
                    "Markdown OKF document is missing frontmatter type.",
                    "Repair frontmatter or regenerate the derived OKF file.",
                )
            if allowed_loose_types is not None and doc_type not in allowed_loose_types:
                self._check_governed_schema(doc, module, issues)
        counts[f"{module}_okf_docs"] = checked

    def _check_derived_okf_count(
        self,
        root: Path,
        module: str,
        expected_count: int,
        issues: list[HealthIssue],
        remediation: str,
    ) -> None:
        index_path = root / "index.md"
        self._check_markdown_doc(index_path, module, issues)
        item_dir = root / "items"
        item_count = len(list(item_dir.glob("*.md"))) if item_dir.exists() else 0
        if item_count != expected_count:
            self._issue(
                issues,
                "warning",
                module,
                "derived_okf_count_mismatch",
                item_dir,
                f"Derived OKF item count {item_count} does not match JSON index count {expected_count}.",
                remediation,
            )
        self._check_markdown_okf(
            root,
            module=module,
            issues=issues,
            counts={},
            allowed_loose_types=set(),
        )

    def _typed_docs(
        self,
        root: Path,
        type_name: str,
        issues: list[HealthIssue],
        module: str,
    ) -> list[MarkdownDoc]:
        docs: list[MarkdownDoc] = []
        if not root.exists():
            return docs
        for path in sorted(root.glob("*.md"), key=lambda item: item.as_posix()):
            if path.name in {"index.md", "log.md"}:
                continue
            doc = self._read_doc(path, module, issues)
            if doc is None:
                continue
            if doc.frontmatter.get("type") == type_name:
                docs.append(doc)
            elif path.name != "board.html":
                self._issue(
                    issues,
                    "error",
                    module,
                    "unexpected_okf_type",
                    path,
                    f"Expected {type_name} document.",
                    "Repair frontmatter or move the file out of this module.",
                )
        return docs

    def _require_fields(
        self,
        doc: MarkdownDoc,
        fields: tuple[str, ...],
        module: str,
        issues: list[HealthIssue],
    ) -> None:
        path = doc.path or Path(".")
        missing = [field for field in fields if field not in doc.frontmatter]
        if missing:
            self._issue(
                issues,
                "error",
                module,
                "missing_required_fields",
                path,
                f"OKF document is missing required fields: {', '.join(missing)}",
                "Rewrite or update the record through Alcove CLI/MCP.",
            )

    def _require_schema(
        self,
        doc: MarkdownDoc,
        expected: str,
        module: str,
        issues: list[HealthIssue],
    ) -> None:
        path = doc.path or Path(".")
        actual = str(doc.frontmatter.get("schema") or "")
        if actual == expected:
            return
        self._issue(
            issues,
            "error",
            module,
            "invalid_okf_schema",
            path,
            f"Expected schema {expected}, found {actual or '<missing>'}.",
            "Rewrite or update the record through Alcove CLI/MCP.",
        )

    def _check_governed_schema(
        self,
        doc: MarkdownDoc,
        module: str,
        issues: list[HealthIssue],
    ) -> None:
        path = doc.path or Path(".")
        doc_type = str(doc.frontmatter.get("type") or "")
        actual = str(doc.frontmatter.get("schema") or "")
        expected = okf_schema_for(doc_type)
        if expected and actual and actual != expected:
            self._issue(
                issues,
                "warning",
                module,
                "invalid_okf_schema",
                path,
                f"Expected schema {expected}, found {actual}.",
                "Rewrite through Alcove CLI/MCP or update the module schema.",
            )
        elif not actual:
            self._issue(
                issues,
                "warning",
                module,
                "missing_okf_schema",
                path,
                "Alcove-governed OKF document is missing schema.",
                "Rewrite through Alcove CLI/MCP or add the module schema.",
            )

    def _check_json_index_count(
        self,
        path: Path,
        module: str,
        item_key: str,
        expected_count: int,
        issues: list[HealthIssue],
        counts: dict[str, int],
        remediation: str,
    ) -> None:
        payload = self._read_json(path, issues, module)
        items = self._dict_list(payload, item_key)
        counts[f"{module}_index_items"] = len(items)
        if not path.exists():
            self._issue(
                issues,
                "warning",
                module,
                "missing_index",
                path,
                "Module JSON index is missing.",
                remediation,
            )
        elif len(items) != expected_count:
            self._issue(
                issues,
                "warning",
                module,
                "index_count_mismatch",
                path,
                f"JSON index count {len(items)} does not match source count {expected_count}.",
                remediation,
            )

    def _check_json_store(
        self,
        path: Path,
        module: str,
        issues: list[HealthIssue],
        counts: dict[str, int],
    ) -> None:
        payload = self._read_json(path, issues, module)
        if not path.exists():
            counts[module] = 0
            return
        if not isinstance(payload, dict):
            self._issue(
                issues,
                "error",
                module,
                "invalid_json_store",
                path,
                "JSON store is not an object.",
                "Repair or restore the JSON store.",
            )
            return
        if module == "tasks":
            counts["tasks"] = len(self._dict_list(payload, "tasks"))
            counts["ideas"] = len(self._dict_list(payload, "ideas"))
            counts["routines"] = len(self._dict_list(payload, "routines"))
        elif module == "projects":
            projects = self._dict_dict(payload, "projects")
            counts["projects"] = len(projects)

    def _check_markdown_doc(
        self,
        path: Path,
        module: str,
        issues: list[HealthIssue],
        *,
        required_type: str = "",
    ) -> None:
        if not path.is_file():
            self._issue(
                issues,
                "warning",
                module,
                "missing_okf_file",
                path,
                "Derived OKF file is missing.",
                "Refresh or rebuild the affected module.",
            )
            return
        doc = self._read_doc(path, module, issues)
        if doc is None:
            return
        doc_type = str(doc.frontmatter.get("type") or "")
        if not doc_type:
            self._issue(
                issues,
                "error",
                module,
                "missing_okf_type",
                path,
                "Markdown OKF file is missing frontmatter type.",
                "Regenerate the derived OKF file.",
            )
        if required_type and doc_type != required_type:
            self._issue(
                issues,
                "error",
                module,
                "unexpected_okf_type",
                path,
                f"Expected OKF type {required_type}, found {doc_type or '<missing>'}.",
                "Regenerate the module index.",
            )
        self._check_governed_schema(doc, module, issues)

    def _read_doc(
        self,
        path: Path,
        module: str,
        issues: list[HealthIssue],
    ) -> MarkdownDoc | None:
        try:
            return self.repo.read_doc(path)
        except OSError as exc:
            self._issue(
                issues,
                "error",
                module,
                "unreadable_markdown",
                path,
                f"Could not read Markdown file: {exc}",
                "Repair filesystem permissions or restore the file.",
            )
            return None

    def _read_json(
        self,
        path: Path,
        issues: list[HealthIssue],
        module: str,
    ) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self._issue(
                issues,
                "error",
                module,
                "invalid_json",
                path,
                f"Could not parse JSON: {exc}",
                "Repair or regenerate the JSON file.",
            )
            return {}
        return data if isinstance(data, dict) else {}

    def _json_list(
        self,
        path: Path,
        key: str,
        issues: list[HealthIssue],
        module: str,
    ) -> list[dict[str, Any]]:
        data = self._read_json(path, issues, module)
        rows = self._dict_list(data, key)
        return [row for row in rows if isinstance(row, dict)]

    def _items(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows = self._dict_list(payload, "items")
        return [row for row in rows if isinstance(row, dict)]

    def _dict_list(self, data: dict[str, Any], key: str) -> list[Any]:
        value = data.get(key)
        return value if isinstance(value, list) else []

    def _dict_dict(self, data: dict[str, Any], key: str) -> dict[str, Any]:
        value = data.get(key)
        return value if isinstance(value, dict) else {}

    def _issue(
        self,
        issues: list[HealthIssue],
        severity: str,
        module: str,
        kind: str,
        path: Path | str,
        message: str,
        remediation: str = "",
    ) -> None:
        issues.append(
            HealthIssue(
                severity=severity,
                module=module,
                kind=kind,
                path=compact_user_path(path),
                message=message,
                remediation=remediation,
            )
        )

    def _status(self, issues: list[HealthIssue]) -> str:
        if any(issue.severity == "error" for issue in issues):
            return "issues"
        if issues:
            return "warnings"
        return "ok"

    def _dedupe_issues(self, issues: list[HealthIssue]) -> list[HealthIssue]:
        seen: set[tuple[str, str, str, str, str]] = set()
        unique: list[HealthIssue] = []
        for issue in issues:
            key = (
                issue.severity,
                issue.module,
                issue.kind,
                issue.path,
                issue.message,
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(issue)
        return unique
