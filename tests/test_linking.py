from __future__ import annotations

from alcove.connectors.github_stars import GitHubStarsConnector, GitHubStarsImportRequest
from alcove.home import AlcoveHome
from alcove.linking import LinkSourceRequest, LinkingModule
from alcove.markdown import MarkdownRepository
from alcove.mounts import AddMountRequest, MountsModule
from alcove.workspace import Workspace


def test_link_source_promotes_connector_item_to_okf_source(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    export_file = tmp_path / "stars.json"
    export_file.write_text(
        """
[
  {
    "full_name": "octopusgarage/alcove",
    "html_url": "https://github.com/OctopusGarage/alcove",
    "description": "Local-first knowledge core.",
    "language": "Python",
    "topics": ["pkm"]
  }
]
""",
        encoding="utf-8",
    )
    GitHubStarsConnector(workspace).import_export(
        GitHubStarsImportRequest(export_file=str(export_file), tags=["stars"])
    )

    result = LinkingModule(workspace).link_source(
        LinkSourceRequest(
            item_path="connectors/github-stars#octopusgarage/alcove",
            topic="ai-knowledge/knowledge-base",
            summary="Useful reference for personal knowledge tooling.",
        )
    )

    assert result["status"] == "linked"
    assert result["source_path"].endswith("octopusgarage-alcove.md")
    source = MarkdownRepository().read_doc(result["source_path"])
    assert source.frontmatter["type"] == "Source"
    assert source.frontmatter["platform"] == "github-stars"
    assert source.frontmatter["resource"] == "https://github.com/OctopusGarage/alcove"
    assert source.frontmatter["legacy_path"] == "connectors/github-stars#octopusgarage/alcove"
    assert source.frontmatter["tags"] == ["pkm", "stars"]


def test_link_source_promotes_global_home_connector_item_to_workspace_okf(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    home = AlcoveHome.init(tmp_path / "home")
    export_file = tmp_path / "stars.json"
    export_file.write_text(
        """
[
  {
    "full_name": "octopusgarage/alcove",
    "html_url": "https://github.com/OctopusGarage/alcove",
    "description": "Local-first knowledge core.",
    "language": "Python",
    "topics": ["pkm"]
  }
]
""",
        encoding="utf-8",
    )
    GitHubStarsConnector(home=home).import_export(
        GitHubStarsImportRequest(export_file=str(export_file), tags=["stars"])
    )

    result = LinkingModule(workspace, home=home).link_source(
        LinkSourceRequest(
            item_path="connectors/github-stars#octopusgarage/alcove",
            topic="ai-knowledge/knowledge-base",
            summary="Useful reference for personal knowledge tooling.",
        )
    )

    assert result["status"] == "linked"
    assert result["workspace"] == str(workspace.root)
    assert result["home"] == str(home.root)
    source = MarkdownRepository().read_doc(result["source_path"])
    assert source.frontmatter["platform"] == "github-stars"
    assert source.frontmatter["resource"] == "https://github.com/OctopusGarage/alcove"


def test_link_source_uses_direct_external_index_lookup_without_search_scan(
    tmp_path,
    monkeypatch,
):
    workspace = Workspace.init(tmp_path / "workspace")
    home = AlcoveHome.init(tmp_path / "home")
    export_file = tmp_path / "stars.json"
    export_file.write_text(
        """
[
  {
    "full_name": "octopusgarage/alcove",
    "html_url": "https://github.com/OctopusGarage/alcove",
    "description": "Local-first knowledge core.",
    "language": "Python",
    "topics": ["pkm"]
  }
]
""",
        encoding="utf-8",
    )
    GitHubStarsConnector(home=home).import_export(
        GitHubStarsImportRequest(export_file=str(export_file), tags=["stars"])
    )

    class BrokenSearchModule:
        def __init__(self, *args, **kwargs):
            raise AssertionError("LinkingModule should not scan SearchModule for external items")

    monkeypatch.setattr("alcove.linking.SearchModule", BrokenSearchModule)

    result = LinkingModule(workspace, home=home).link_source(
        LinkSourceRequest(
            item_path="connectors/github-stars#octopusgarage/alcove",
            topic="ai-knowledge/knowledge-base",
        )
    )

    assert result["status"] == "linked"


def test_link_source_uses_direct_mount_index_lookup_without_search_scan(
    tmp_path,
    monkeypatch,
):
    workspace = Workspace.init(tmp_path / "workspace")
    source = tmp_path / "external"
    source.mkdir()
    (source / "note.md").write_text("# Mounted Note\n\nUseful mounted reference.", encoding="utf-8")
    mounts = MountsModule(workspace)
    mount = mounts.add(AddMountRequest(path=str(source), name="Archive"))
    mounts.scan(mount.id)

    class BrokenSearchModule:
        def __init__(self, *args, **kwargs):
            raise AssertionError("LinkingModule should not scan SearchModule for mounted items")

    monkeypatch.setattr("alcove.linking.SearchModule", BrokenSearchModule)

    result = LinkingModule(workspace).link_source(
        LinkSourceRequest(
            item_path=f"mounts/{mount.id}#note.md",
            topic="ai-knowledge/knowledge-base",
        )
    )

    assert result["status"] == "linked"
    source_doc = MarkdownRepository().read_doc(result["source_path"])
    assert source_doc.frontmatter["platform"] == "mounts"
    assert source_doc.frontmatter["legacy_path"] == f"mounts/{mount.id}#note.md"
