from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from alcove.automations import AutomationsModule
from alcove.blog_monitor import BlogMonitorModule
from alcove.connector_sources import ConnectorSourceRegistry
from alcove.dashboard import DASHBOARD_SNAPSHOT_VERSION
from alcove.health_planner import HealthPlannerHygieneMixin
from alcove.health_registry import HealthCheckContext, home_health_checks, required_home_path_names
from alcove.health_repairs import HealthRepairModule
from alcove.health_types import HealthIssue
from alcove.health_validation import HealthValidationMixin
from alcove.home import AlcoveHome
from alcove.markdown import MarkdownRepository
from alcove.mounts import MountIndexPolicy
from alcove.okf_catalog import CATALOG_FILES
from alcove.paths import compact_user_path
from alcove.pins import PIN_REQUIRED_FIELDS, PIN_SCHEMA
from alcove.prompt_health import PromptHealthAdapter
from alcove.prompts import PROMPT_REQUIRED_FIELDS, PROMPT_SCHEMA
from alcove.publishers import PublisherModule
from alcove.radars import RadarModule
from alcove.validate import ValidateModule
from alcove.watchers import WatcherModule
from alcove.workspace import Workspace


class HealthModule(HealthPlannerHygieneMixin, HealthValidationMixin):
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
        fixture_context: bool = False,
    ) -> dict[str, Any]:
        actions: list[dict[str, Any]] = []
        if fix:
            actions.extend(
                HealthRepairModule(
                    home=self.home,
                    workspace=self.workspace,
                    repo=self.repo,
                ).safe_rebuilds(
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
            self._check_home(
                self.home,
                issues,
                counts,
                strict=strict,
                fixture_context=fixture_context,
            )
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

    def _check_workspace(
        self,
        workspace: Workspace,
        issues: list[HealthIssue],
        counts: dict[str, int],
        *,
        strict: bool,
        fixture_context: bool = False,
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
        fixture_context: bool = False,
    ) -> None:
        paths = home.paths()
        for name in required_home_path_names():
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
        for check in home_health_checks():
            try:
                result = check.run(
                    self,
                    HealthCheckContext(
                        home=home,
                        strict=strict,
                        fixture_context=fixture_context,
                    ),
                )
                issues.extend(result.issues)
                counts.update(result.counts)
            except Exception as exc:
                self._issue(
                    issues,
                    "error",
                    check.name,
                    "health_check_failed",
                    home.root,
                    f"Home health check failed: {check.name}: {exc}",
                    "Run `alcove health --json` again after repairing the reported module.",
                )

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

    def _check_prompt_quality(
        self,
        home: AlcoveHome,
        issues: list[HealthIssue],
        counts: dict[str, int],
    ) -> None:
        report = PromptHealthAdapter(home).report()
        counts.update(report["counts"])
        for item in report["issues"]:
            issues.append(HealthIssue(**item))

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
            self._check_mount_index_policy(mount, root / "mounts.json", mount_id, issues)
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

    def _check_mount_index_policy(
        self,
        mount: dict[str, Any],
        path: Path,
        mount_id: str,
        issues: list[HealthIssue],
    ) -> None:
        policy = self._dict_dict(mount, "index_policy")
        if not policy:
            return
        try:
            MountIndexPolicy(
                profile=str(policy.get("profile") or "raw"),
                include=[str(item) for item in self._dict_list(policy, "include")],
                exclude=[str(item) for item in self._dict_list(policy, "exclude")],
                max_file_size_kb=int(policy.get("max_file_size_kb") or 976),
            ).resolve()
        except (TypeError, ValueError) as exc:
            self._issue(
                issues,
                "error",
                "mounts",
                "invalid_mount_index_policy",
                path,
                f"Mount {mount_id} has invalid index policy: {exc}",
                "Run `alcove mount update <mount-id> --profile docs` or repair mounts.json.",
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
        counts["radar_runs"] = self._check_json_tree_recursive(
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
