from __future__ import annotations

from typing import Any

from alcove.connectors.apple_notes import AppleNotesConnector
from alcove.connectors.chrome_bookmarks import ChromeBookmarksConnector
from alcove.connectors.github_stars import GitHubStarsConnector
from alcove.home import AlcoveHome
from alcove.workspace import Workspace


CONNECTOR_REFRESHERS = {
    "apple-notes": AppleNotesConnector,
    "github-stars": GitHubStarsConnector,
    "chrome-bookmarks": ChromeBookmarksConnector,
}


def refresh_connector_sources(
    *,
    workspace: Workspace | None,
    home: AlcoveHome | None,
    connector: str = "",
    stale_only: bool = True,
    source_id: str = "",
) -> dict[str, Any]:
    reports = [
        connector_class(workspace, home=home).refresh_sources(
            stale_only=stale_only,
            source_id=source_id,
        )
        for connector_id, connector_class in CONNECTOR_REFRESHERS.items()
        if connector in {"", connector_id}
    ]
    return summarize_connector_refresh_reports(reports)


def summarize_connector_refresh_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    sources = [
        source
        for report in reports
        for source in report.get("sources", [])
        if isinstance(source, dict)
    ]
    return {
        "refreshed": _sum_report_count(reports, "refreshed"),
        "skipped": _sum_report_count(reports, "skipped"),
        "reused": _sum_report_count(reports, "reused"),
        "errors": _sum_report_count(reports, "errors"),
        "sources": sources,
    }


def _sum_report_count(reports: list[dict[str, Any]], key: str) -> int:
    return sum(int(report.get(key) or 0) for report in reports)
