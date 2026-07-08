from __future__ import annotations

from alcove.connectors.github_stars import GitHubStarsConnector, GitHubStarsImportRequest
from alcove.linking import LinkSourceRequest, LinkingModule
from alcove.markdown import MarkdownRepository
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
