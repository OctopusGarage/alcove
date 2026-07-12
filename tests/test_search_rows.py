from __future__ import annotations

from alcove.search_rows import SearchRowBuilder


def test_mount_search_row_exposes_unified_read_reference() -> None:
    row = SearchRowBuilder(None).mount_item(
        {
            "mount_id": "archive",
            "mount_name": "Archive",
            "relative_path": "notes/agent.md",
            "title": "Agent Notes",
            "text": "Readable mount content.",
            "indexed_at": "2026-07-12T00:00:00+00:00",
        }
    )

    assert row["source_ref"] == "mounts/archive#notes/agent.md"
    assert row["read_ref"] == "mounts/archive#notes/agent.md"
    assert row["read_command"] == ""
    assert "mount source reference" in row["read_hint"]
    assert row["display_label"] == "Agent Notes"
    assert row["source_label"] == "Archive"


def test_connector_search_row_exposes_unified_read_reference() -> None:
    row = SearchRowBuilder(None).connector_item(
        "github-stars",
        {
            "connector": "github-stars",
            "connector_name": "GitHub Stars",
            "relative_path": "octocat/octopusgarage/alcove",
            "title": "octopusgarage/alcove",
            "text": "Useful project.",
        },
    )

    assert row["fetch_ref"] == "connectors/github-stars#octocat/octopusgarage/alcove"
    assert row["read_ref"] == row["fetch_ref"]
    assert row["read_command"] == row["fetch_command"]
    assert row["source_ref"] == row["fetch_ref"]
    assert "connector fetch" in row["read_hint"]
