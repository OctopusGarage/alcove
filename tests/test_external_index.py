from __future__ import annotations

import json

import pytest

from alcove.external_index import ExternalIndexStore, ExternalItemReference


def test_external_item_reference_owns_external_path_format():
    connector_ref = ExternalItemReference.connector("github-stars", "octopusgarage/alcove")
    mount_ref = ExternalItemReference.mount("archive", "notes/index.md")

    assert connector_ref.path == "connectors/github-stars#octopusgarage/alcove"
    assert mount_ref.path == "mounts/archive#notes/index.md"
    assert ExternalItemReference.parse(connector_ref.path) == connector_ref
    assert ExternalItemReference.parse(mount_ref.path) == mount_ref
    assert ExternalItemReference.parse_connector(connector_ref.path) == connector_ref
    assert ExternalItemReference.parse_optional("knowledge/source.md") is None

    with pytest.raises(ValueError, match="Connector item path"):
        ExternalItemReference.parse_connector(mount_ref.path)


def test_external_index_store_filters_malformed_items_at_read_seam(tmp_path):
    root = tmp_path / "connectors"
    path = root / "demo" / "index.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "connector": "demo",
                "items": [
                    "not-a-dict",
                    {"relative_path": "missing-title"},
                    {"title": "Missing Relative Path"},
                    {
                        "relative_path": "valid",
                        "title": "Valid",
                        "text": "Searchable text",
                        "tags": [],
                        "status": "active",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    store = ExternalIndexStore(root)

    assert store.find_connector_item("demo", "missing-title") is None
    assert store.find_connector_item("demo", "valid")["title"] == "Valid"
