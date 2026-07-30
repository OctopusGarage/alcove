from alcove.mcp_connector_requests import (
    apple_notes_index_request,
    apple_notes_local_import_request,
    chrome_bookmarks_index_request,
    chrome_bookmarks_local_import_request,
    github_stars_index_request,
    github_stars_url_import_request,
)


def test_mcp_apple_notes_index_request_preserves_fields() -> None:
    request = apple_notes_index_request(export_dir="/tmp/notes-export", tags=["notes"])

    assert request.export_dir == "/tmp/notes-export"
    assert request.tags == ["notes"]


def test_mcp_apple_notes_local_import_request_defaults_adapter_values() -> None:
    request = apple_notes_local_import_request()

    assert request.export_dir == ""
    assert request.source_id == "local"
    assert request.tags == []


def test_mcp_github_stars_index_request_preserves_fields() -> None:
    request = github_stars_index_request(export_file="/tmp/stars.json", tags=["github"])

    assert request.export_file == "/tmp/stars.json"
    assert request.tags == ["github"]


def test_mcp_github_stars_url_import_request_preserves_fields() -> None:
    request = github_stars_url_import_request(
        source="https://github.com/octocat?tab=stars",
        export_file="/tmp/octocat-stars.json",
        tags=["stars"],
        limit=20,
        max_pages=2,
    )

    assert request.source == "https://github.com/octocat?tab=stars"
    assert request.export_file == "/tmp/octocat-stars.json"
    assert request.tags == ["stars"]
    assert request.limit == 20
    assert request.max_pages == 2


def test_mcp_github_stars_url_import_request_defaults_adapter_values() -> None:
    request = github_stars_url_import_request(source="octocat")

    assert request.export_file == ""
    assert request.tags == []
    assert request.limit == 0
    assert request.max_pages == 0


def test_mcp_chrome_bookmarks_index_request_preserves_fields() -> None:
    request = chrome_bookmarks_index_request(export_file="/tmp/bookmarks.html", tags=["browser"])

    assert request.export_file == "/tmp/bookmarks.html"
    assert request.tags == ["browser"]


def test_mcp_chrome_bookmarks_local_import_request_preserves_fields() -> None:
    request = chrome_bookmarks_local_import_request(
        source_file="/tmp/Bookmarks",
        profile="Work",
        source_id="work",
        tags=["chrome"],
    )

    assert request.source_file == "/tmp/Bookmarks"
    assert request.profile == "Work"
    assert request.source_id == "work"
    assert request.tags == ["chrome"]


def test_mcp_chrome_bookmarks_local_import_request_defaults_adapter_values() -> None:
    request = chrome_bookmarks_local_import_request()

    assert request.source_file == ""
    assert request.profile == "Default"
    assert request.source_id == "default"
    assert request.tags == []
