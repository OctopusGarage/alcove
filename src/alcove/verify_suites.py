from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import shlex
from typing import Any


@dataclass(frozen=True)
class VerifySuite:
    id: str
    command: str
    directory_name: str
    directory_var: str
    report_file: str
    report_key: str
    env_var: str
    evidence_section: str

    def directory(self, root: Path) -> Path:
        return root / self.directory_name

    def report_path(self, root: Path) -> Path:
        return self.directory(root) / self.report_file


def verify_suite_manifest() -> list[VerifySuite]:
    return [
        VerifySuite(
            id="isolated",
            command="scripts/verify/smoke-isolated.sh",
            directory_name="smoke",
            directory_var="smoke_root",
            report_file="smoke-report.json",
            report_key="smoke_report",
            env_var="ALCOVE_SMOKE_TMP",
            evidence_section="smoke",
        ),
        VerifySuite(
            id="real_home",
            command="scripts/verify/smoke-real-home.sh",
            directory_name="real-home",
            directory_var="real_home_dir",
            report_file="real-home-smoke-report.json",
            report_key="real_home_report",
            env_var="ALCOVE_REAL_SMOKE_REPORT_DIR",
            evidence_section="real_home",
        ),
        VerifySuite(
            id="real_integrations",
            command="scripts/verify/smoke-real-integrations.sh",
            directory_name="real-integrations",
            directory_var="real_integrations_dir",
            report_file="real-integrations-summary.json",
            report_key="real_integrations_report",
            env_var="ALCOVE_REAL_INTEGRATION_DIR",
            evidence_section="real_integrations",
        ),
        VerifySuite(
            id="agent_clients",
            command="scripts/verify/smoke-agent-clients.sh",
            directory_name="agent-clients",
            directory_var="agent_clients_dir",
            report_file="agent-client-smoke-report.json",
            report_key="agent_client_report",
            env_var="ALCOVE_AGENT_CLIENT_SMOKE_DIR",
            evidence_section="agent_client_smoke",
        ),
        VerifySuite(
            id="mcp_matrix",
            command="scripts/verify/smoke-mcp-matrix.sh",
            directory_name="mcp-matrix",
            directory_var="mcp_matrix_dir",
            report_file="mcp-matrix-report.json",
            report_key="mcp_matrix_report",
            env_var="ALCOVE_MCP_MATRIX_DIR",
            evidence_section="mcp_matrix",
        ),
        VerifySuite(
            id="dashboard_browser",
            command="scripts/verify/smoke-dashboard-browser.sh",
            directory_name="dashboard-browser",
            directory_var="dashboard_browser_dir",
            report_file="dashboard-browser-report.json",
            report_key="dashboard_browser_report",
            env_var="ALCOVE_DASHBOARD_BROWSER_DIR",
            evidence_section="dashboard_browser",
        ),
        VerifySuite(
            id="radar_reports",
            command="scripts/verify/smoke-radar-reports.sh",
            directory_name="radar-reports",
            directory_var="radar_reports_dir",
            report_file="radar-reports-report.json",
            report_key="radar_reports_report",
            env_var="ALCOVE_RADAR_REPORTS_DIR",
            evidence_section="radar_reports",
        ),
        VerifySuite(
            id="export_restore",
            command="scripts/verify/smoke-export-restore.sh",
            directory_name="export-restore",
            directory_var="export_restore_dir",
            report_file="export-restore-report.json",
            report_key="export_restore_report",
            env_var="ALCOVE_EXPORT_RESTORE_DIR",
            evidence_section="export_restore",
        ),
        VerifySuite(
            id="messy_inbox",
            command="scripts/verify/smoke-messy-inbox.sh",
            directory_name="messy-inbox",
            directory_var="messy_inbox_dir",
            report_file="messy-inbox-report.json",
            report_key="messy_inbox_report",
            env_var="ALCOVE_MESSY_INBOX_DIR",
            evidence_section="messy_inbox",
        ),
    ]


def eval_report_paths(root: str | Path) -> dict[str, Path]:
    base = Path(root)
    paths: dict[str, Path] = {}
    for suite in verify_suite_manifest():
        paths[suite.directory_var] = suite.directory(base)
        paths[suite.report_key] = suite.report_path(base)
    paths["real_integrations_dir"] = paths["real_integrations_dir"]
    paths["smoke_root"] = paths["smoke_root"]
    return paths


def suite_manifest_json(root: str | Path | None = None) -> dict[str, Any]:
    base = Path(root) if root is not None else None
    suites = []
    for suite in verify_suite_manifest():
        row: dict[str, Any] = {
            "id": suite.id,
            "command": suite.command,
            "directory_name": suite.directory_name,
            "directory_var": suite.directory_var,
            "report_file": suite.report_file,
            "report_key": suite.report_key,
            "env_var": suite.env_var,
            "evidence_section": suite.evidence_section,
        }
        if base is not None:
            row["directory"] = str(suite.directory(base))
            row["report_path"] = str(suite.report_path(base))
        suites.append(row)
    return {"schema": "alcove.verify_suites.v1", "suites": suites}


def shell_assignments(root: str | Path) -> str:
    paths = eval_report_paths(root)
    lines = []
    for key, value in paths.items():
        if key.endswith("_report"):
            continue
        lines.append(f"{key}={shlex.quote(str(value))}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print Alcove verify suite manifest.")
    parser.add_argument("--root", required=True)
    parser.add_argument("--shell", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.shell:
        print(shell_assignments(args.root))
        return 0
    print(json.dumps(suite_manifest_json(args.root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
