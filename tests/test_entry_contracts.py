from __future__ import annotations

from alcove.entry_contracts import entry_contract_matrix, validate_entry_contract_matrix
from alcove.cli import main
from alcove.mcp_toolsets import resolve_mcp_toolset


def test_entry_contract_matrix_covers_profiles_clients_toolsets_and_paths():
    payload = entry_contract_matrix(home_part="--home /tmp/alcove-home")

    assert payload["schema"] == "alcove/agent-entry-contract-matrix/v1"
    assert {row["profile"] for row in payload["contracts"]} == {
        "hub",
        "workspace",
        "managed-kb",
        "global",
    }
    assert {row["client"] for row in payload["contracts"] if row["profile"] == "hub"} == {
        "codex",
        "claude",
    }
    assert all(row["install_path"] and row["status_path"] for row in payload["contracts"])
    assert all(
        row["home_scope"]["explicit"] == "--home /tmp/alcove-home" for row in payload["contracts"]
    )


def test_entry_contract_validation_is_deterministic_and_model_free():
    first = validate_entry_contract_matrix(home_part="--home /tmp/alcove-home")
    second = validate_entry_contract_matrix(home_part="--home /tmp/alcove-home")

    assert first["status"] == second["status"] == "pass"
    assert first["errors"] == second["errors"] == []
    assert first["model_calls"] == second["model_calls"] == 0
    assert first["contracts"] == second["contracts"]


def test_entry_contract_cli_and_mcp_selection_are_deterministic(tmp_path, capsys):
    code = main(
        [
            "entry",
            "contract",
            "--validate",
            "--home",
            str(tmp_path / ".alcove"),
            "--json",
        ]
    )
    output = capsys.readouterr().out
    lite_name, lite_tools = resolve_mcp_toolset("lite")
    full_name, full_tools = resolve_mcp_toolset("full")

    assert code == 0
    assert '"status": "pass"' in output
    assert lite_name == "lite"
    assert "alcove_radar_proposal_list" in lite_tools
    assert "alcove_radar_proposal_accept" not in lite_tools
    assert full_name == "full"
    assert "alcove_radar_proposal_accept" in full_tools
