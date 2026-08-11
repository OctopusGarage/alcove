from __future__ import annotations

import json

import pytest

from alcove.verify_suites import EvalEvidencePaths, main, shell_assignments, suite_manifest_json


def test_eval_evidence_paths_expose_expected_report_contracts(tmp_path):
    paths = EvalEvidencePaths.from_root(tmp_path)
    legacy = paths.as_legacy_dict()
    packet_kwargs = paths.build_eval_packet_kwargs()

    assert legacy["smoke_root"] == tmp_path / "smoke"
    assert legacy["smoke_report"] == tmp_path / "smoke" / "smoke-report.json"
    assert packet_kwargs["mcp_matrix_report"] == (
        tmp_path / "mcp-matrix" / "mcp-matrix-report.json"
    )
    assert packet_kwargs["messy_inbox_report"] == (
        tmp_path / "messy-inbox" / "messy-inbox-report.json"
    )
    with pytest.raises(KeyError, match="Unknown verification report key"):
        paths.report("not_a_report")


def test_suite_manifest_json_includes_runnable_commands_and_report_paths(tmp_path):
    manifest = suite_manifest_json(tmp_path)
    suites = {suite["id"]: suite for suite in manifest["suites"]}

    assert manifest["schema"] == "alcove.verify_suites.v1"
    assert suites["isolated"]["command"] == "scripts/verify/smoke-isolated.sh"
    assert suites["real_integrations"]["env_var"] == "ALCOVE_REAL_INTEGRATION_DIR"
    assert suites["dashboard_browser"]["report_path"] == str(
        tmp_path / "dashboard-browser" / "dashboard-browser-report.json"
    )


def test_verify_suites_cli_prints_json_and_shell_assignments(tmp_path, capsys):
    json_code = main(["--root", str(tmp_path), "--json"])
    json_output = capsys.readouterr()
    shell_code = main(["--root", str(tmp_path), "--shell"])
    shell_output = capsys.readouterr()

    assert json_code == 0
    assert json.loads(json_output.out)["suites"][0]["id"] == "isolated"
    assert shell_code == 0
    assert f"smoke_root={tmp_path / 'smoke'}" in shell_output.out
    assert shell_assignments(tmp_path) == shell_output.out.rstrip("\n")
