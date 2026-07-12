from __future__ import annotations

from pathlib import Path

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
    assert result["concept_path"] == ""
    assert result["concept_status"] == "source_only"
    assert "create_concept=True" in result["concept_reason"]
    assert result["source"]["title"] == "octopusgarage/alcove"
    assert result["source"]["resource"] == "https://github.com/OctopusGarage/alcove"
    assert result["source"]["tags"] == ["pkm", "stars"]
    assert result["source"]["confidence"] == 0.5
    assert "Useful reference" in result["source"]["notes_excerpt"]
    assert "notes_excerpt_truncated" in result["source"]
    assert "notes_excerpt_omitted_chars" in result["source"]
    assert result["source_relative_path"] == (
        "knowledge/sources/github-stars/ai-knowledge/octopusgarage-alcove.md"
    )
    assert result["source"]["read_command"].endswith(
        "&& cat knowledge/sources/github-stars/ai-knowledge/octopusgarage-alcove.md"
    )
    assert str(workspace.root) in result["source"]["read_command"]
    assert result["source_path"] not in result["source"]["read_command"]
    assert "cat '~/" not in result["source"]["read_command"]
    assert "workspace context" in result["source"]["full_source_hint"]
    source = MarkdownRepository().read_doc(result["source_path"])
    assert source.frontmatter["type"] == "Source"
    assert source.frontmatter["platform"] == "github-stars"
    assert source.frontmatter["resource"] == "https://github.com/OctopusGarage/alcove"
    assert source.frontmatter["legacy_path"] == "connectors/github-stars#octopusgarage/alcove"
    assert source.frontmatter["tags"] == ["pkm", "stars"]
    assert source.frontmatter["confidence"] == 0.5
    assert "Local-first knowledge core." in source.body
    assert "Language: Python" in source.body
    assert "Tags: pkm, stars" in source.body


def test_link_source_shell_read_path_uses_expandable_home(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    module = LinkingModule(workspace)

    command_path = module._shell_read_path(Path.home() / "alcove source.md")

    assert command_path == '"$HOME/alcove source.md"'
    assert "'~/" not in command_path


def test_link_source_marks_clipped_source_excerpt(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    export_file = tmp_path / "stars.json"
    export_file.write_text(
        """
[
  {
    "full_name": "octopusgarage/long-note",
    "html_url": "https://github.com/OctopusGarage/long-note",
    "description": "Long context """
        + ("detail " * 100)
        + """",
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
            item_path="connectors/github-stars#octopusgarage/long-note",
            topic="ai-knowledge/knowledge-base",
            summary="Useful reference.",
        )
    )

    assert result["source"]["notes_excerpt_truncated"] is True
    assert result["source"]["notes_excerpt_omitted_chars"] > 0


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
    assert "Useful mounted reference." in source_doc.body
