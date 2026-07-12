from alcove.external_index import ExternalItemReference
from alcove.external_presentation import ExternalIndexedItemPresenter


def test_connector_presentation_owns_display_fetch_and_public_fields():
    item = {
        "source_kind": "connector",
        "connector": "github-stars",
        "connector_name": "GitHub Stars",
        "type": "GitHub Star",
        "title": "octopusgarage/alcove",
        "relative_path": "octocat/octopusgarage/alcove",
        "resource": "https://github.com/OctopusGarage/alcove",
        "text": "Local-first knowledge core.",
        "tags": ["pkm"],
        "status": "active",
        "indexed_at": "2026-07-10T00:00:00+00:00",
        "path": "~/private/export.json",
    }
    ref = ExternalItemReference.connector("github-stars", "octocat/octopusgarage/alcove")

    row = ExternalIndexedItemPresenter(ref, item).connector_fields()
    public_item = ExternalIndexedItemPresenter(ref, item).public_item()

    assert row == {
        "display_id": "github-stars/octopusgarage-alcove",
        "display_label": "octopusgarage/alcove",
        "source_id": "github-stars",
        "source_label": "GitHub Stars",
        "origin_label": "GitHub Stars",
        "fetch_ref": "connectors/github-stars#octocat/octopusgarage/alcove",
        "fetch_command": (
            "alcove connector fetch connectors/github-stars#octocat/octopusgarage/alcove --json"
        ),
    }
    assert "path" not in public_item
    assert public_item["title"] == "octopusgarage/alcove"


def test_apple_notes_presentation_redacts_secret_like_text():
    item = {
        "source_kind": "connector",
        "connector": "apple-notes",
        "connector_name": "Apple Notes",
        "type": "Apple Note",
        "title": "Token note",
        "relative_path": "notes/x-coredata%3A%2F%2Fnote/note.json",
        "folder_path": "iCloud/Secrets",
        "text": "api key sk-real-looking-secret-1234567890",
        "status": "active",
    }
    ref = ExternalItemReference.connector("apple-notes", item["relative_path"])

    presenter = ExternalIndexedItemPresenter(ref, item)

    assert presenter.connector_fields()["display_label"] == "Token note"
    assert presenter.connector_fields()["source_label"] == "Apple Notes · iCloud/Secrets"
    assert presenter.origin_label() == "Apple Notes / iCloud/Secrets"
    assert presenter.safe_text() == "[redacted: secret-like connector content]"


def test_mount_presentation_owns_source_ref_and_read_hint():
    item = {
        "source_kind": "mount",
        "mount_id": "research-archive",
        "mount_name": "Research Archive",
        "type": "Mounted Item",
        "title": "Agent Notes",
        "relative_path": "notes/agent.md",
        "path": "~/archives/notes/agent.md",
        "text": "Mounted research note.",
        "status": "active",
        "indexed_at": "2026-07-10T00:00:00+00:00",
    }

    presenter = ExternalIndexedItemPresenter.from_item(item)

    assert presenter is not None
    assert presenter.dashboard_item() == {
        "title": "Agent Notes",
        "type": "Mounted Item",
        "path": "notes/agent.md",
        "source": "Research Archive",
        "resource": "mounts/research-archive#notes/agent.md",
        "status": "active",
        "notes": "Mounted research note.",
        "updated_at": "2026-07-10T00:00:00+00:00",
        "display_id": "mounts/research-archive#notes/agent.md",
        "display_label": "Agent Notes",
        "source_id": "research-archive",
        "source_label": "Research Archive",
        "origin_label": "Research Archive",
        "source_ref": "mounts/research-archive#notes/agent.md",
        "read_hint": (
            "Use the mount source reference to inspect the external file "
            "from the configured mount root."
        ),
        "read_ref_available": True,
        "read_ref_pattern": "mounts/<id>#<relative-path>",
    }
