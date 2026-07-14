from __future__ import annotations

from typing import Any

from alcove.application_base import _Capability
from alcove.doctor import DoctorModule
from alcove.exporter import ExportModule
from alcove.gardener import GardenerModule
from alcove.health import HealthModule
from alcove.installer import InstallerModule
from alcove.okf_catalog import OkfCatalogModule
from alcove.validate import ValidateModule


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

    def okf_catalog_build_payload(self, *, include_all_status: bool = False) -> dict[str, Any]:
        if self.runtime.home is None:
            raise ValueError("Alcove home is required")
        return self.runtime.scope_payload(
            OkfCatalogModule(self.runtime.home).build(include_all_status=include_all_status)
        )

    def health_payload(
        self,
        *,
        fix: bool = False,
        strict: bool = False,
        deep: bool = False,
        refresh_stale_connectors: bool = False,
        refresh_all_connectors: bool = False,
        fixture_context: bool = False,
    ) -> dict[str, Any]:
        if self.runtime.home is None and self.runtime.workspace is None:
            raise ValueError("Alcove home or workspace is required")
        report = HealthModule(home=self.runtime.home, workspace=self.runtime.workspace).check(
            fix=fix,
            strict=strict,
            deep=deep,
            refresh_stale_connectors=refresh_stale_connectors,
            refresh_all_connectors=refresh_all_connectors,
            fixture_context=fixture_context,
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
