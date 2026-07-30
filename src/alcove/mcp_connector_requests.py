from __future__ import annotations

from alcove.connectors.apple_notes import AppleNotesImportRequest, AppleNotesLocalImportRequest
from alcove.connectors.chrome_bookmarks import (
    ChromeBookmarksImportRequest,
    ChromeBookmarksLocalImportRequest,
)
from alcove.connectors.github_stars import GitHubStarsImportRequest, GitHubStarsUrlImportRequest


def apple_notes_index_request(
    *,
    export_dir: str,
    tags: list[str] | None = None,
) -> AppleNotesImportRequest:
    """Build the Apple Notes export index request shared by MCP adapter surfaces."""
    return AppleNotesImportRequest(export_dir=export_dir, tags=tags or [])


def apple_notes_local_import_request(
    *,
    export_dir: str = "",
    source_id: str = "local",
    tags: list[str] | None = None,
) -> AppleNotesLocalImportRequest:
    """Build the local Apple Notes import request shared by MCP adapter surfaces."""
    return AppleNotesLocalImportRequest(export_dir=export_dir, source_id=source_id, tags=tags or [])


def github_stars_index_request(
    *,
    export_file: str,
    tags: list[str] | None = None,
) -> GitHubStarsImportRequest:
    """Build the GitHub Stars export index request shared by MCP adapter surfaces."""
    return GitHubStarsImportRequest(export_file=export_file, tags=tags or [])


def github_stars_url_import_request(
    *,
    source: str,
    export_file: str = "",
    tags: list[str] | None = None,
    limit: int = 0,
    max_pages: int = 0,
) -> GitHubStarsUrlImportRequest:
    """Build the GitHub Stars URL import request shared by MCP adapter surfaces."""
    return GitHubStarsUrlImportRequest(
        source=source,
        export_file=export_file,
        tags=tags or [],
        limit=limit,
        max_pages=max_pages,
    )


def chrome_bookmarks_index_request(
    *,
    export_file: str,
    tags: list[str] | None = None,
) -> ChromeBookmarksImportRequest:
    """Build the Chrome Bookmarks export index request shared by MCP adapter surfaces."""
    return ChromeBookmarksImportRequest(export_file=export_file, tags=tags or [])


def chrome_bookmarks_local_import_request(
    *,
    source_file: str = "",
    profile: str = "Default",
    source_id: str = "default",
    tags: list[str] | None = None,
) -> ChromeBookmarksLocalImportRequest:
    """Build the local Chrome Bookmarks import request shared by MCP adapter surfaces."""
    return ChromeBookmarksLocalImportRequest(
        source_file=source_file,
        profile=profile,
        source_id=source_id,
        tags=tags or [],
    )
