from alcove.application import AlcoveApplication
from alcove.capability_payloads import CapabilityPayloadPresenter
from alcove.home import AlcoveHome
from alcove.mounts import AddMountRequest, MountsModule
from alcove.runtime import AlcoveRuntime
from alcove.workspace import Workspace


def test_capability_payload_presenter_scopes_and_shapes_path_rows(tmp_path):
    workspace = Workspace.init(tmp_path / "kb")
    home = AlcoveHome.init(tmp_path / "home")
    presenter = CapabilityPayloadPresenter(AlcoveRuntime(workspace=workspace, home=home))
    knowledge_path = workspace.root / "knowledge" / "tags" / "rare.md"

    payload = presenter.scope(
        {
            "issues": presenter.workspace_relative_path_rows(
                [
                    {"kind": "orphan_tag", "path": str(knowledge_path)},
                    {"kind": "external", "path": str(home.root / "pins" / "pin.md")},
                ],
                workspace.root,
            )
        }
    )

    assert payload["workspace"] == str(workspace.root)
    assert payload["home"] == str(home.root)
    assert payload["issues"][0]["path"] == "knowledge/tags/rare.md"
    assert payload["issues"][1]["path"].endswith("/home/pins/pin.md")


def test_mount_scan_payload_uses_public_mount_summary(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    source = tmp_path / "mounted-repo"
    source.mkdir()
    (source / "note.md").write_text("# Mounted Note\n\nSearchable.", encoding="utf-8")
    mount = MountsModule(home=home).add(
        AddMountRequest(path=str(source), name="Mounted Repo", tags=["smoke"])
    )

    payload = AlcoveApplication(AlcoveRuntime(home=home)).external.mount_scan_payload(mount.id)

    assert payload["mount"]["id"] == mount.id
    assert payload["mount"]["path_label"] == "mounted-repo"
    assert payload["mount"]["index_ref"] == f"mounts/okf/{mount.id}/index.md"
    assert payload["mount"]["scan_command"] == f"alcove mount scan {mount.id} --json"
    assert "path" not in payload["mount"]
