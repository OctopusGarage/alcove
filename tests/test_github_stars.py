from __future__ import annotations

import json

from alcove.connectors.github_stars import GitHubStarsConnector, GitHubStarsImportRequest
from alcove.search import SearchModule, SearchRequest
from alcove.workspace import Workspace


def test_github_stars_index_imports_repository_export(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    export_file = tmp_path / "stars.json"
    export_file.write_text(
        json.dumps(
            {
                "repositories": [
                    {
                        "full_name": "octopusgarage/clipsmith",
                        "html_url": "https://github.com/OctopusGarage/clipsmith",
                        "description": "Capture web and social posts into bundles.",
                        "language": "Python",
                        "topics": ["capture", "agent-tools"],
                        "stargazers_count": 42,
                        "updated_at": "2026-07-08T00:00:00Z",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = GitHubStarsConnector(workspace).import_export(
        GitHubStarsImportRequest(export_file=str(export_file), tags=["github-stars"])
    )

    assert result["scanned"] == 1
    assert result["index_path"].endswith(".alcove/connectors/github-stars/index.json")
    assert result["items"][0]["title"] == "octopusgarage/clipsmith"
    assert result["items"][0]["resource"] == "https://github.com/OctopusGarage/clipsmith"
    assert result["items"][0]["tags"] == ["agent-tools", "capture", "github-stars"]


def test_search_includes_imported_github_stars(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    export_file = tmp_path / "stars.json"
    export_file.write_text(
        json.dumps(
            [
                {
                    "nameWithOwner": "octopusgarage/alcove",
                    "url": "https://github.com/OctopusGarage/alcove",
                    "description": "Local-first personal knowledge core.",
                    "primaryLanguage": {"name": "Python"},
                    "repositoryTopics": {"nodes": [{"topic": {"name": "knowledge-base"}}]},
                    "stargazerCount": 100,
                    "updatedAt": "2026-07-08T00:00:00Z",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    GitHubStarsConnector(workspace).import_export(
        GitHubStarsImportRequest(export_file=str(export_file), tags=["pkm"])
    )

    rows = SearchModule(workspace).search(SearchRequest(query="knowledge core"))

    assert len(rows) == 1
    assert {
        "root": "connectors",
        "type": "GitHub Star",
        "title": "octopusgarage/alcove",
        "platform": "github-stars",
        "topic": "Python",
        "tags": ["knowledge-base", "pkm"],
        "status": "active",
    }.items() <= rows[0].items()
    assert rows[0]["resource"] == "https://github.com/OctopusGarage/alcove"
