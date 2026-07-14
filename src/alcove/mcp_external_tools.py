from __future__ import annotations

from typing import Any

from alcove.connectors.apple_notes import AppleNotesImportRequest, AppleNotesLocalImportRequest
from alcove.connectors.chrome_bookmarks import (
    ChromeBookmarksImportRequest,
    ChromeBookmarksLocalImportRequest,
)
from alcove.connectors.github_stars import GitHubStarsImportRequest, GitHubStarsUrlImportRequest
from alcove.linking import LinkSourceRequest
from alcove.mcp_context import McpInvocationContext, agent_payload
from alcove.mcp_registrar import McpToolRegistrar
from alcove.mounts import AddMountRequest, MountIndexPolicy


def register_mcp_external_tools(
    registrar: McpToolRegistrar,
    context: McpInvocationContext,
) -> None:
    tool = registrar.tool

    @tool
    def alcove_mount_list(
        workspace: str = "",
        status: str = "active",
        home: str = "",
    ) -> dict[str, Any]:
        """List configured Alcove mounts."""
        return context.scoped_app(workspace, home).external.mount_list_payload(status)

    @tool
    def alcove_link_source(
        item_path: str,
        topic: str,
        workspace: str = "",
        home: str = "",
        summary: str = "",
        create_concept: bool = False,
    ) -> dict[str, Any]:
        """Promote indexed external evidence into a governed OKF Source."""
        return context.scoped_app(workspace, home).external.link_source_payload(
            LinkSourceRequest(
                item_path=item_path,
                topic=topic,
                summary=summary,
                create_concept=create_concept,
            )
        )

    @tool
    def alcove_mount_add(
        path: str,
        workspace: str = "",
        home: str = "",
        name: str = "",
        mount_type: str = "local-folder",
        tags: list[str] | None = None,
        profile: str = "raw",
        include: list[str] | None = None,
        exclude: list[str] | None = None,
        max_file_size_kb: int = 976,
    ) -> dict[str, Any]:
        """Add a mounted external source."""
        return context.scoped_app(workspace, home).external.mount_add_payload(
            AddMountRequest(
                path=path,
                name=name,
                mount_type=mount_type,
                tags=tags or [],
                index_policy=MountIndexPolicy(
                    profile=profile,
                    include=include or [],
                    exclude=exclude or [],
                    max_file_size_kb=max_file_size_kb,
                ),
            )
        )

    @tool
    def alcove_mount_update_policy(
        mount_id: str,
        workspace: str = "",
        home: str = "",
        profile: str = "",
        include: list[str] | None = None,
        exclude: list[str] | None = None,
        max_file_size_kb: int = 0,
    ) -> dict[str, Any]:
        """Update a mounted source index policy."""
        return context.scoped_app(workspace, home).external.mount_update_policy_payload(
            mount_id,
            MountIndexPolicy(
                profile=profile,
                include=include or [],
                exclude=exclude or [],
                max_file_size_kb=max_file_size_kb,
            ),
        )

    @tool
    def alcove_mount_scan(
        workspace: str = "",
        home: str = "",
        mount_id: str | None = None,
        include_diagnostics: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Refresh mount indexes so AI-led investigation has current local-file evidence."""
        return context.scoped_app(workspace, home).external.mount_scan_payload(
            mount_id,
            include_diagnostics=include_diagnostics,
            dry_run=dry_run,
        )

    @tool
    def alcove_connector_fetch(
        item_path: str, workspace: str = "", home: str = ""
    ) -> dict[str, Any]:
        """Lazy-fetch detail for an indexed connector candidate before final synthesis."""
        return context.scoped_app(workspace, home).external.connector_fetch_payload(item_path)

    @tool
    def alcove_connector_status(
        workspace: str = "",
        home: str = "",
        connector: str = "",
    ) -> dict[str, Any]:
        """Show registered connector sources and freshness status."""
        return agent_payload(
            context.scoped_app(workspace, home).external.connector_status_payload(connector)
        )

    @tool
    def alcove_connector_refresh(
        workspace: str = "",
        home: str = "",
        connector: str = "",
        source_id: str = "",
        stale_only: bool = True,
    ) -> dict[str, Any]:
        """Refresh connector indexes so candidate discovery uses current external evidence."""
        return context.scoped_app(workspace, home).external.connector_refresh_payload(
            connector=connector,
            source_id=source_id,
            stale_only=stale_only,
        )

    @tool
    def alcove_connector_apple_notes_index(
        export_dir: str,
        workspace: str = "",
        home: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Index a deterministic Apple Notes export directory."""
        return context.scoped_app(workspace, home).external.apple_notes_index_payload(
            AppleNotesImportRequest(export_dir=export_dir, tags=tags or [])
        )

    @tool
    def alcove_connector_apple_notes_import_local(
        workspace: str = "",
        home: str = "",
        export_dir: str = "",
        source_id: str = "local",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Export local Notes.app notes into Alcove, then index them."""
        return context.scoped_app(workspace, home).external.apple_notes_import_local_payload(
            AppleNotesLocalImportRequest(
                export_dir=export_dir,
                source_id=source_id,
                tags=tags or [],
            )
        )

    @tool
    def alcove_connector_github_stars_index(
        export_file: str,
        workspace: str = "",
        home: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Index a GitHub Stars JSON export."""
        return context.scoped_app(workspace, home).external.github_stars_index_payload(
            GitHubStarsImportRequest(export_file=export_file, tags=tags or [])
        )

    @tool
    def alcove_connector_github_stars_import_url(
        source: str,
        workspace: str = "",
        home: str = "",
        export_file: str = "",
        tags: list[str] | None = None,
        limit: int = 0,
        max_pages: int = 0,
    ) -> dict[str, Any]:
        """Fetch starred repositories from a GitHub stars page or username, then index them."""
        return context.scoped_app(workspace, home).external.github_stars_import_url_payload(
            GitHubStarsUrlImportRequest(
                source=source,
                export_file=export_file,
                tags=tags or [],
                limit=limit,
                max_pages=max_pages,
            )
        )

    @tool
    def alcove_connector_chrome_bookmarks_index(
        export_file: str,
        workspace: str = "",
        home: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Index a Chrome Bookmarks JSON file or Netscape bookmarks HTML export."""
        return context.scoped_app(workspace, home).external.chrome_bookmarks_index_payload(
            ChromeBookmarksImportRequest(export_file=export_file, tags=tags or [])
        )

    @tool
    def alcove_connector_chrome_bookmarks_import_local(
        workspace: str = "",
        home: str = "",
        source_file: str = "",
        profile: str = "Default",
        source_id: str = "default",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Index the local Chrome profile Bookmarks file and register it for refresh."""
        return context.scoped_app(workspace, home).external.chrome_bookmarks_import_local_payload(
            ChromeBookmarksLocalImportRequest(
                source_file=source_file,
                profile=profile,
                source_id=source_id,
                tags=tags or [],
            )
        )

    @tool
    def alcove_export_global(output_dir: str, home: str = "") -> dict[str, Any]:
        """Export Alcove Home global data."""
        return context.scoped_app("", home).system.export_global_payload(output_dir)

    @tool
    def alcove_export_kb(kb: str, output_dir: str, home: str = "") -> dict[str, Any]:
        """Export a registered managed knowledge base."""
        return context.scoped_app("", home).system.export_kb_payload(kb, output_dir)

    @tool
    def alcove_export_all(output_dir: str, home: str = "") -> dict[str, Any]:
        """Export Alcove Home and all registered managed knowledge bases."""
        return context.scoped_app("", home).system.export_all_payload(output_dir)
