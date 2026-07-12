from __future__ import annotations

import json

from alcove.connector_sources import ConnectorSourceRegistry
from alcove.connectors.chrome_bookmarks import (
    ChromeBookmarksConnector,
    ChromeBookmarksImportRequest,
    ChromeBookmarksLocalImportRequest,
)
from alcove.connectors.fetch import ConnectorFetchModule
from alcove.external_index import ExternalIndexStore, ExternalItemReference
from alcove.markdown import MarkdownRepository
from alcove.search import SearchModule, SearchRequest
from alcove.workspace import Workspace


def _write_chrome_json(path, *, extra_children=None):
    children = [
        {
            "type": "url",
            "name": "Alcove Docs",
            "url": "https://octopusgarage.github.io/alcove/",
            "date_added": "13300000000000000",
        },
        {
            "type": "folder",
            "name": "Agents",
            "children": [
                {
                    "type": "url",
                    "name": "Codegraph",
                    "url": "https://github.com/colbymchenry/codegraph",
                    "date_added": "13300000001000000",
                }
            ],
        },
    ]
    if extra_children:
        children.extend(extra_children)
    path.write_text(
        json.dumps(
            {
                "roots": {
                    "bookmark_bar": {
                        "type": "folder",
                        "name": "Bookmarks Bar",
                        "children": children,
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_chrome_bookmarks_index_imports_chrome_json(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    export_file = tmp_path / "Bookmarks"
    _write_chrome_json(export_file)

    result = ChromeBookmarksConnector(workspace).import_export(
        ChromeBookmarksImportRequest(export_file=str(export_file), tags=["browser"])
    )

    assert result["scanned"] == 2
    assert result["index_path"].endswith(".alcove/connectors/chrome-bookmarks/index.json")
    assert result["items"][0]["type"] == "Chrome Bookmark"
    assert result["items"][0]["connector"] == "chrome-bookmarks"
    assert result["items"][0]["folder_path"] == "Bookmarks Bar"
    assert result["items"][0]["resource"] == "https://octopusgarage.github.io/alcove/"
    assert result["items"][1]["folder_path"] == "Bookmarks Bar/Agents"
    assert result["items"][1]["tags"] == ["browser"]

    found = ExternalIndexStore(workspace.paths().state / "connectors").find_item(
        ExternalItemReference.connector(
            "chrome-bookmarks",
            result["items"][1]["relative_path"],
        )
    )
    assert found is not None
    assert found["title"] == "Codegraph"


def test_chrome_bookmarks_index_imports_netscape_html_export(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    export_file = tmp_path / "bookmarks.html"
    export_file.write_text(
        """<!DOCTYPE NETSCAPE-Bookmark-file-1>
<DL><p>
  <DT><H3>Agents</H3>
  <DL><p>
    <DT><A HREF="https://github.com/colbymchenry/codegraph" ADD_DATE="1710000000">Codegraph</A>
  </DL><p>
</DL><p>
""",
        encoding="utf-8",
    )

    result = ChromeBookmarksConnector(workspace).import_export(
        ChromeBookmarksImportRequest(export_file=str(export_file), tags=["bookmarks"])
    )

    assert result["scanned"] == 1
    assert result["items"][0]["title"] == "Codegraph"
    assert result["items"][0]["folder_path"] == "Agents"
    assert result["items"][0]["date_added"] == "2024-03-09T16:00:00+00:00"


def test_chrome_bookmarks_import_writes_okf_markdown_connector_index(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    export_file = tmp_path / "Bookmarks"
    _write_chrome_json(export_file)

    ChromeBookmarksConnector(workspace).import_export(
        ChromeBookmarksImportRequest(export_file=str(export_file), tags=["browser"])
    )

    repo = MarkdownRepository()
    okf_root = workspace.paths().state / "connectors" / "chrome-bookmarks" / "okf"
    index = repo.read_doc(okf_root / "index.md")
    item_paths = sorted((okf_root / "items").glob("*.md"))
    item = repo.read_doc(item_paths[0])
    assert index.frontmatter["type"] == "Connector Index"
    assert index.frontmatter["connector_id"] == "chrome-bookmarks"
    assert index.frontmatter["item_count"] == 2
    assert item.frontmatter["type"] == "Chrome Bookmark"
    assert item.frontmatter["schema"] == "okf/connector-item/v1"
    assert item.frontmatter["resource"].startswith("https://")


def test_chrome_bookmarks_import_keeps_duplicate_bookmarks_addressable(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    export_file = tmp_path / "Bookmarks"
    export_file.write_text(
        json.dumps(
            {
                "roots": {
                    "bookmark_bar": {
                        "type": "folder",
                        "name": "Bookmarks Bar",
                        "children": [
                            {
                                "type": "url",
                                "name": "Codegraph",
                                "url": "https://github.com/colbymchenry/codegraph",
                                "date_added": "13300000001000000",
                            },
                            {
                                "type": "url",
                                "name": "Codegraph",
                                "url": "https://github.com/colbymchenry/codegraph",
                                "date_added": "13300000003000000",
                            },
                        ],
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = ChromeBookmarksConnector(workspace).import_export(
        ChromeBookmarksImportRequest(export_file=str(export_file), tags=["browser"])
    )

    relative_paths = [item["relative_path"] for item in result["items"]]
    okf_items = list(
        (workspace.paths().state / "connectors" / "chrome-bookmarks" / "okf" / "items").glob("*.md")
    )
    assert result["scanned"] == 2
    assert len(relative_paths) == len(set(relative_paths))
    assert len(okf_items) == 2


def test_chrome_bookmarks_refresh_diff_counts_duplicate_bookmarks(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    source_file = tmp_path / "Bookmarks"
    source_file.write_text(
        json.dumps(
            {
                "roots": {
                    "bookmark_bar": {
                        "type": "folder",
                        "name": "Bookmarks Bar",
                        "children": [
                            {
                                "type": "url",
                                "name": "Codegraph",
                                "url": "https://github.com/colbymchenry/codegraph",
                                "date_added": "13300000001000000",
                            },
                            {
                                "type": "url",
                                "name": "Codegraph",
                                "url": "https://github.com/colbymchenry/codegraph",
                                "date_added": "13300000003000000",
                            },
                        ],
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    connector = ChromeBookmarksConnector(workspace)
    connector.import_local(
        ChromeBookmarksLocalImportRequest(source_file=str(source_file), source_id="default")
    )

    refresh = connector.refresh_sources(stale_only=False, source_id="default")

    assert refresh["skipped"] == 1
    assert refresh["sources"][0]["diff"] == {
        "added": [],
        "removed": [],
        "updated": [],
        "unchanged": 2,
    }


def test_chrome_bookmarks_import_local_registers_source_and_refreshes(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    source_file = tmp_path / "Bookmarks"
    _write_chrome_json(source_file)
    connector = ChromeBookmarksConnector(workspace)

    result = connector.import_local(
        ChromeBookmarksLocalImportRequest(
            source_file=str(source_file),
            source_id="default",
            tags=["bookmarks"],
        )
    )

    status = ConnectorSourceRegistry(workspace).status(connector="chrome-bookmarks")
    assert result["exported"] == 2
    assert status["count"] == 1
    assert status["sources"][0]["id"] == "default"
    assert status["sources"][0]["source"] == "Chrome Bookmarks: Default"

    _write_chrome_json(
        source_file,
        extra_children=[
            {
                "type": "url",
                "name": "Alcove Repository",
                "url": "https://github.com/OctopusGarage/alcove",
                "date_added": "13300000002000000",
            }
        ],
    )
    refresh = connector.refresh_sources(stale_only=False, source_id="default")

    assert refresh["refreshed"] == 1
    assert refresh["sources"][0]["diff"]["added"] == ["Alcove Repository"]
    assert refresh["sources"][0]["scanned"] == 3


def test_search_and_fetch_include_imported_chrome_bookmarks(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    export_file = tmp_path / "Bookmarks"
    _write_chrome_json(export_file)
    result = ChromeBookmarksConnector(workspace).import_export(
        ChromeBookmarksImportRequest(export_file=str(export_file), tags=["browser"])
    )

    search_results = SearchModule(workspace).search(SearchRequest(query="codegraph", limit=5))
    fetched = ConnectorFetchModule(workspace).fetch(
        f"connectors/chrome-bookmarks#{result['items'][1]['relative_path']}"
    )

    assert any(
        row["title"] == "Codegraph" and row["type"] == "Chrome Bookmark" for row in search_results
    )
    assert fetched["item"]["title"] == "Codegraph"
    assert fetched["detail"]["resource"] == "https://github.com/colbymchenry/codegraph"
