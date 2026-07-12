from __future__ import annotations

import json
from urllib.error import HTTPError

from alcove.connector_sources import ConnectorSourceRegistry
from alcove.connectors.fetch import ConnectorFetchModule
from alcove.connectors.github_stars import (
    GitHubStarsConnector,
    GitHubStarsImportRequest,
    GitHubStarsUrlImportRequest,
)
from alcove.markdown import MarkdownRepository
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


def test_connector_status_includes_unregistered_indexed_connector(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    export_file = tmp_path / "stars.json"
    export_file.write_text(
        json.dumps(
            [
                {
                    "full_name": "octopusgarage/alcove",
                    "html_url": "https://github.com/OctopusGarage/alcove",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    GitHubStarsConnector(workspace).import_export(GitHubStarsImportRequest(str(export_file)))

    status = ConnectorSourceRegistry(workspace).status()

    assert status["count"] == 1
    assert {
        "connector": "github-stars",
        "id": "github-stars",
        "item_count": 1,
        "status": "fresh",
    }.items() <= status["sources"][0].items()
    assert status["sources"][0]["source"] == "GitHub Stars index"


def test_connector_status_prefers_registered_source_over_index_fallback(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    export_file = tmp_path / "stars.json"
    export_file.write_text(
        json.dumps(
            [
                {
                    "full_name": "octopusgarage/alcove",
                    "html_url": "https://github.com/OctopusGarage/alcove",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    GitHubStarsConnector(workspace).import_export(GitHubStarsImportRequest(str(export_file)))
    ConnectorSourceRegistry(workspace).upsert_github_stars(
        source_id="octocat",
        source="https://github.com/octocat?tab=stars",
        username="octocat",
        tags=["github-stars"],
        export_file=export_file,
        index_path=workspace.paths().state / "connectors" / "github-stars" / "index.json",
        item_count=1,
        checked_at="2026-07-10T00:00:00+00:00",
    )

    status = ConnectorSourceRegistry(workspace).status()

    assert status["count"] == 1
    assert status["sources"][0]["id"] == "octocat"
    assert status["sources"][0]["source"] == "https://github.com/octocat?tab=stars"


def test_github_stars_import_writes_okf_markdown_connector_index(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    export_file = tmp_path / "stars.json"
    export_file.write_text(
        json.dumps(
            [
                {
                    "full_name": "octopusgarage/alcove",
                    "html_url": "https://github.com/OctopusGarage/alcove",
                    "description": "Local-first personal knowledge core.",
                    "language": "Python",
                    "topics": ["knowledge-base"],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    GitHubStarsConnector(workspace).import_export(
        GitHubStarsImportRequest(export_file=str(export_file), tags=["github-stars"])
    )

    repo = MarkdownRepository()
    okf_root = workspace.paths().state / "connectors" / "github-stars" / "okf"
    index = repo.read_doc(okf_root / "index.md")
    item_paths = sorted((okf_root / "items").glob("*.md"))
    item = repo.read_doc(item_paths[0])
    assert index.frontmatter["type"] == "Connector Index"
    assert index.frontmatter["schema"] == "okf/connector-index/v1"
    assert index.frontmatter["connector_id"] == "github-stars"
    assert index.frontmatter["item_count"] == 1
    assert item.frontmatter["type"] == "GitHub Star"
    assert item.frontmatter["schema"] == "okf/connector-item/v1"
    assert item.frontmatter["resource"] == "https://github.com/OctopusGarage/alcove"
    assert "Local-first personal knowledge core." in item.body


def test_github_stars_import_removes_stale_okf_items(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    export_file = tmp_path / "stars.json"
    export_file.write_text(
        json.dumps(
            [
                {
                    "full_name": "octopusgarage/alcove",
                    "html_url": "https://github.com/OctopusGarage/alcove",
                },
                {
                    "full_name": "octopusgarage/clipsmith",
                    "html_url": "https://github.com/OctopusGarage/clipsmith",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    connector = GitHubStarsConnector(workspace)
    connector.import_export(GitHubStarsImportRequest(export_file=str(export_file)))
    okf_item_dir = workspace.paths().state / "connectors" / "github-stars" / "okf" / "items"
    assert len(list(okf_item_dir.glob("*.md"))) == 2
    export_file.write_text(
        json.dumps(
            [
                {
                    "full_name": "octopusgarage/alcove",
                    "html_url": "https://github.com/OctopusGarage/alcove",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    connector.import_export(GitHubStarsImportRequest(export_file=str(export_file)))

    okf_items = [
        MarkdownRepository().read_doc(path)
        for path in sorted(okf_item_dir.glob("*.md"), key=lambda item: item.as_posix())
    ]
    assert [item.frontmatter["title"] for item in okf_items] == ["octopusgarage/alcove"]


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


def test_search_tags_include_imported_github_stars(tmp_path):
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
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    GitHubStarsConnector(workspace).import_export(
        GitHubStarsImportRequest(export_file=str(export_file), tags=["pkm"])
    )

    tags = SearchModule(workspace).tags()

    assert {"tag": "knowledge-base", "count": 1} in tags
    assert {"tag": "pkm", "count": 1} in tags


def test_github_stars_import_url_fetches_exports_and_indexes(tmp_path, monkeypatch):
    workspace = Workspace.init(tmp_path / "workspace")
    connector = GitHubStarsConnector(workspace)
    pages = {
        1: [
            {
                "full_name": "octopusgarage/alcove",
                "html_url": "https://github.com/OctopusGarage/alcove",
                "description": "Local-first personal knowledge core.",
                "language": "Python",
                "topics": ["knowledge-base"],
                "stargazers_count": 100,
                "updated_at": "2026-07-08T00:00:00Z",
            }
        ],
        2: [],
    }

    def fake_fetch(username: str, *, page: int, per_page: int):
        assert username == "octocat"
        assert per_page == 100
        return pages[page]

    monkeypatch.setattr(connector, "_fetch_starred_page", fake_fetch)

    result = connector.import_url(
        GitHubStarsUrlImportRequest(
            source="https://github.com/octocat?tab=stars",
            tags=["github-stars"],
        )
    )

    assert result["username"] == "octocat"
    assert result["exported"] == 1
    assert result["scanned"] == 1
    assert result["export_file"].endswith("octocat-starred.json")
    assert (workspace.paths().state / "connectors" / "github-stars" / "exports").is_dir()
    assert result["items"][0]["title"] == "octopusgarage/alcove"
    source = ConnectorSourceRegistry(workspace=workspace).get("github-stars", "octocat")
    assert source["source"] == "https://github.com/octocat?tab=stars"
    assert source["refresh"]["status"] == "fresh"
    assert source["refresh"]["item_count"] == 1
    assert source["tags"] == ["github-stars"]
    source_doc = MarkdownRepository().read_doc(
        workspace.paths().state / "connectors" / "github-stars" / "okf" / "sources" / "octocat.md"
    )
    assert source_doc.frontmatter["type"] == "Connector Source"
    assert source_doc.frontmatter["schema"] == "okf/connector-source/v1"
    assert source_doc.frontmatter["source_id"] == "octocat"
    assert source_doc.frontmatter["item_count"] == 1


def test_github_stars_import_url_accepts_username_and_limit(tmp_path, monkeypatch):
    workspace = Workspace.init(tmp_path / "workspace")
    connector = GitHubStarsConnector(workspace)

    def fake_fetch(username: str, *, page: int, per_page: int):
        assert username == "octocat"
        return [
            {
                "full_name": "one/repo",
                "html_url": "https://github.com/one/repo",
            },
            {
                "full_name": "two/repo",
                "html_url": "https://github.com/two/repo",
            },
        ]

    monkeypatch.setattr(connector, "_fetch_starred_page", fake_fetch)

    result = connector.import_url(GitHubStarsUrlImportRequest(source="octocat", limit=1))

    assert result["exported"] == 1
    assert result["items"][0]["title"] == "one/repo"


def test_github_stars_import_url_keeps_multiple_sources_in_one_connector_index(
    tmp_path,
    monkeypatch,
):
    workspace = Workspace.init(tmp_path / "workspace")
    connector = GitHubStarsConnector(workspace)
    repos_by_user = {
        "octocat": [
            {
                "full_name": "octopusgarage/alcove",
                "html_url": "https://github.com/OctopusGarage/alcove",
                "description": "Local-first personal knowledge core.",
                "language": "Python",
            }
        ],
        "OtherUser": [
            {
                "full_name": "other/bookmarks",
                "html_url": "https://github.com/other/bookmarks",
                "description": "Second source repo.",
                "language": "TypeScript",
            }
        ],
    }

    def fake_fetch(username: str, *, page: int, per_page: int):
        if page > 1:
            return []
        return repos_by_user[username]

    monkeypatch.setattr(connector, "_fetch_starred_page", fake_fetch)

    connector.import_url(GitHubStarsUrlImportRequest(source="octocat", tags=["first"]))
    connector.import_url(GitHubStarsUrlImportRequest(source="OtherUser", tags=["second"]))

    rows = SearchModule(workspace).search(
        SearchRequest(query="", type_filter="GitHub Star", limit=10)
    )

    assert {row["title"] for row in rows} == {
        "octopusgarage/alcove",
        "other/bookmarks",
    }
    assert {row["path"] for row in rows} == {
        "connectors/github-stars#octocat/octopusgarage/alcove",
        "connectors/github-stars#otheruser/other/bookmarks",
    }
    payload = json.loads(
        (workspace.paths().state / "connectors" / "github-stars" / "index.json").read_text(
            encoding="utf-8"
        )
    )
    assert {item["source_id"] for item in payload["items"]} == {"octocat", "otheruser"}

    fetched = ConnectorFetchModule(workspace).fetch(
        "connectors/github-stars#octocat/octopusgarage/alcove"
    )
    assert fetched["item"]["title"] == "octopusgarage/alcove"
    assert fetched["detail"]["resource"] == "https://github.com/OctopusGarage/alcove"
    assert "path" not in fetched["item"]
    assert "path" not in fetched["detail"]


def test_github_stars_refresh_replaces_only_the_matching_source_items(
    tmp_path,
    monkeypatch,
):
    workspace = Workspace.init(tmp_path / "workspace")
    connector = GitHubStarsConnector(workspace)
    repos_by_user = {
        "octocat": [
            {
                "full_name": "octopusgarage/alcove",
                "html_url": "https://github.com/OctopusGarage/alcove",
            }
        ],
        "OtherUser": [
            {
                "full_name": "other/bookmarks",
                "html_url": "https://github.com/other/bookmarks",
            }
        ],
    }

    def fake_fetch(username: str, *, page: int, per_page: int):
        if page > 1:
            return []
        return repos_by_user[username]

    monkeypatch.setattr(connector, "_fetch_starred_page", fake_fetch)

    connector.import_url(GitHubStarsUrlImportRequest(source="octocat"))
    connector.import_url(GitHubStarsUrlImportRequest(source="OtherUser"))
    repos_by_user["octocat"] = [
        {
            "full_name": "octopusgarage/alcove-next",
            "html_url": "https://github.com/OctopusGarage/alcove-next",
        }
    ]

    result = connector.refresh_sources(source_id="octocat")

    rows = SearchModule(workspace).search(
        SearchRequest(query="", type_filter="GitHub Star", limit=10)
    )
    assert result["refreshed"] == 1
    assert {row["title"] for row in rows} == {
        "octopusgarage/alcove-next",
        "other/bookmarks",
    }
    assert {row["path"] for row in rows} == {
        "connectors/github-stars#octocat/octopusgarage/alcove-next",
        "connectors/github-stars#otheruser/other/bookmarks",
    }


def test_github_stars_fetch_accepts_unique_legacy_unscoped_item_path(
    tmp_path,
    monkeypatch,
):
    workspace = Workspace.init(tmp_path / "workspace")
    connector = GitHubStarsConnector(workspace)

    def fake_fetch(username: str, *, page: int, per_page: int):
        if page > 1:
            return []
        return [
            {
                "full_name": "octopusgarage/alcove",
                "html_url": "https://github.com/OctopusGarage/alcove",
            }
        ]

    monkeypatch.setattr(connector, "_fetch_starred_page", fake_fetch)
    connector.import_url(GitHubStarsUrlImportRequest(source="octocat"))

    fetched = ConnectorFetchModule(workspace).fetch("connectors/github-stars#octopusgarage/alcove")

    assert fetched["relative_path"] == "octopusgarage/alcove"
    assert fetched["item"]["relative_path"] == "octocat/octopusgarage/alcove"
    assert fetched["item"]["source_id"] == "octocat"
    assert "path" not in fetched["item"]


def test_github_stars_source_status_marks_stale_after_ttl(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    registry = ConnectorSourceRegistry(workspace=workspace)
    registry.upsert_github_stars(
        source_id="octocat",
        source="https://github.com/octocat?tab=stars",
        username="octocat",
        tags=["github-stars"],
        export_file=tmp_path / "stars.json",
        index_path=workspace.paths().state / "connectors" / "github-stars" / "index.json",
        item_count=445,
        checked_at="2026-07-07T00:00:00+00:00",
        changed_at="2026-07-07T00:00:00+00:00",
    )

    status = registry.status(
        now="2026-07-09T01:00:00+00:00",
        default_ttl_hours=24,
    )

    assert status["count"] == 1
    assert {
        "connector": "github-stars",
        "id": "octocat",
        "status": "stale",
        "item_count": 445,
    }.items() <= status["sources"][0].items()


def test_github_stars_refresh_stale_updates_registered_source(
    tmp_path,
    monkeypatch,
):
    workspace = Workspace.init(tmp_path / "workspace")
    connector = GitHubStarsConnector(workspace)
    registry = ConnectorSourceRegistry(workspace=workspace)
    registry.upsert_github_stars(
        source_id="octocat",
        source="https://github.com/octocat?tab=stars",
        username="octocat",
        tags=["github-stars"],
        export_file=workspace.paths().state
        / "connectors"
        / "github-stars"
        / "exports"
        / "octocat-starred.json",
        index_path=workspace.paths().state / "connectors" / "github-stars" / "index.json",
        item_count=1,
        checked_at="2026-07-07T00:00:00+00:00",
        changed_at="2026-07-07T00:00:00+00:00",
    )

    def fake_fetch(username: str, *, page: int, per_page: int):
        assert username == "octocat"
        if page > 1:
            return []
        return [
            {
                "full_name": "octopusgarage/alcove",
                "html_url": "https://github.com/OctopusGarage/alcove",
                "description": "Local-first personal knowledge core.",
                "language": "Python",
                "topics": ["knowledge-base"],
                "stargazers_count": 100,
            },
            {
                "full_name": "octopusgarage/clipsmith",
                "html_url": "https://github.com/OctopusGarage/clipsmith",
            },
        ]

    monkeypatch.setattr(connector, "_fetch_starred_page", fake_fetch)

    result = connector.refresh_sources(
        stale_only=True,
        now="2026-07-09T01:00:00+00:00",
        default_ttl_hours=24,
    )

    assert result["refreshed"] == 1
    assert result["skipped"] == 0
    assert result["sources"][0]["exported"] == 2
    source = ConnectorSourceRegistry(workspace=workspace).get("github-stars", "octocat")
    assert source["refresh"]["status"] == "fresh"
    assert source["refresh"]["item_count"] == 2


def test_github_stars_refresh_reports_added_removed_updated_and_unchanged(
    tmp_path,
    monkeypatch,
):
    workspace = Workspace.init(tmp_path / "workspace")
    connector = GitHubStarsConnector(workspace)
    export_file = (
        workspace.paths().state / "connectors" / "github-stars" / "exports" / "octocat-starred.json"
    )
    export_file.parent.mkdir(parents=True)
    export_file.write_text(
        json.dumps(
            [
                {
                    "full_name": "old/removed",
                    "html_url": "https://github.com/old/removed",
                    "description": "gone",
                },
                {
                    "full_name": "old/changed",
                    "html_url": "https://github.com/old/changed",
                    "description": "before",
                },
                {
                    "full_name": "old/same",
                    "html_url": "https://github.com/old/same",
                    "description": "same",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    ConnectorSourceRegistry(workspace=workspace).upsert_github_stars(
        source_id="octocat",
        source="https://github.com/octocat?tab=stars",
        username="octocat",
        tags=["github-stars"],
        export_file=export_file,
        index_path=workspace.paths().state / "connectors" / "github-stars" / "index.json",
        item_count=3,
        checked_at="2026-07-07T00:00:00+00:00",
        changed_at="2026-07-07T00:00:00+00:00",
    )

    def fake_fetch(username: str, *, page: int, per_page: int):
        if page > 1:
            return []
        return [
            {
                "full_name": "old/changed",
                "html_url": "https://github.com/old/changed",
                "description": "after",
            },
            {
                "full_name": "old/same",
                "html_url": "https://github.com/old/same",
                "description": "same",
            },
            {
                "full_name": "new/added",
                "html_url": "https://github.com/new/added",
                "description": "new",
            },
        ]

    monkeypatch.setattr(connector, "_fetch_starred_page", fake_fetch)

    result = connector.refresh_sources(source_id="octocat")

    diff = result["sources"][0]["diff"]
    assert diff["added"] == ["new/added"]
    assert diff["removed"] == ["old/removed"]
    assert diff["updated"] == ["old/changed"]
    assert diff["unchanged"] == 1


def test_github_stars_refresh_handles_not_modified_without_reindexing(
    tmp_path,
    monkeypatch,
):
    workspace = Workspace.init(tmp_path / "workspace")
    connector = GitHubStarsConnector(workspace)
    export_file = (
        workspace.paths().state / "connectors" / "github-stars" / "exports" / "octocat-starred.json"
    )
    export_file.parent.mkdir(parents=True)
    export_file.write_text(
        json.dumps(
            [
                {
                    "full_name": "old/same",
                    "html_url": "https://github.com/old/same",
                    "description": "same",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    ConnectorSourceRegistry(workspace=workspace).upsert_github_stars(
        source_id="octocat",
        source="https://github.com/octocat?tab=stars",
        username="octocat",
        tags=["github-stars"],
        export_file=export_file,
        index_path=workspace.paths().state / "connectors" / "github-stars" / "index.json",
        item_count=1,
        checked_at="2026-07-07T00:00:00+00:00",
        changed_at="2026-07-07T00:00:00+00:00",
    )

    def fake_fetch_if_changed(*args, **kwargs):
        return {"not_modified": True, "repos": [], "etag": '"same"'}

    monkeypatch.setattr(connector, "_fetch_starred_repositories_if_changed", fake_fetch_if_changed)

    result = connector.refresh_sources(source_id="octocat")

    assert result["refreshed"] == 0
    assert result["skipped"] == 1
    assert result["sources"][0]["status"] == "not_modified"
    assert result["sources"][0]["diff"] == {
        "added": [],
        "removed": [],
        "updated": [],
        "unchanged": 1,
    }
    source = ConnectorSourceRegistry(workspace=workspace).get("github-stars", "octocat")
    assert source["refresh"]["status"] == "fresh"
    assert source["refresh"]["etag"] == '"same"'


def test_github_stars_page_response_treats_http_304_as_not_modified(tmp_path, monkeypatch):
    workspace = Workspace.init(tmp_path / "workspace")
    connector = GitHubStarsConnector(workspace)

    class Headers:
        def get(self, key: str):
            return '"same"' if key == "ETag" else ""

    def fake_urlopen(request, timeout: int):
        raise HTTPError(
            url="https://api.github.com/users/octocat/starred",
            code=304,
            msg="Not Modified",
            hdrs=Headers(),
            fp=None,
        )

    monkeypatch.setattr("alcove.connectors.github_stars.urlopen", fake_urlopen)

    response = connector._fetch_starred_page_response(
        "octocat",
        page=1,
        per_page=100,
        etag='"old"',
    )

    assert response == {"not_modified": True, "items": [], "etag": '"same"'}


def test_github_stars_refresh_records_source_error_without_aborting(tmp_path, monkeypatch):
    workspace = Workspace.init(tmp_path / "workspace")
    connector = GitHubStarsConnector(workspace)
    export_file = (
        workspace.paths().state / "connectors" / "github-stars" / "exports" / "octocat-starred.json"
    )
    ConnectorSourceRegistry(workspace=workspace).upsert_github_stars(
        source_id="octocat",
        source="https://github.com/octocat?tab=stars",
        username="octocat",
        tags=["github-stars"],
        export_file=export_file,
        index_path=workspace.paths().state / "connectors" / "github-stars" / "index.json",
        item_count=1,
        checked_at="2026-07-07T00:00:00+00:00",
        changed_at="2026-07-07T00:00:00+00:00",
    )

    def fake_fetch(username: str, *, page: int, per_page: int):
        raise RuntimeError("GitHub Stars API request failed: HTTP 502")

    monkeypatch.setattr(connector, "_fetch_starred_page", fake_fetch)

    result = connector.refresh_sources(source_id="octocat")

    assert result["refreshed"] == 0
    assert result["skipped"] == 0
    assert result["errors"] == 1
    assert result["sources"][0]["status"] == "error"
    assert "HTTP 502" in result["sources"][0]["error"]
    source = ConnectorSourceRegistry(workspace=workspace).get("github-stars", "octocat")
    assert source["refresh"]["status"] == "error"
    assert "HTTP 502" in source["refresh"]["last_error"]
