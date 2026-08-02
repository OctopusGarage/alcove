from __future__ import annotations

from typing import Any

from alcove.mcp_context import McpInvocationContext
from alcove.mcp_pin_requests import pin_add_request, pin_update_request
from alcove.mcp_project_requests import project_add_request
from alcove.mcp_prompt_tools import register_mcp_prompt_tools
from alcove.mcp_registrar import McpToolRegistrar


def register_mcp_global_tools(
    registrar: McpToolRegistrar,
    context: McpInvocationContext,
) -> None:
    tool = registrar.tool
    register_mcp_prompt_tools(registrar, context)

    @tool
    def alcove_pin_add(
        title: str,
        workspace: str = "",
        home: str = "",
        description: str = "",
        summary: str = "",
        content: str = "",
        kind: str = "regular",
        tags: list[str] | None = None,
        priority: str = "medium",
        source_refs: list[str] | None = None,
        resources: list[str] | None = None,
        content_format: str = "text",
    ) -> dict[str, Any]:
        """Create a pinned personal note through the governed global write path."""
        return context.scoped_app(workspace, home).global_home.pin_add_payload(
            pin_add_request(
                title=title,
                description=description,
                summary=summary,
                content=content,
                kind=kind,
                tags=tags,
                priority=priority,
                source_refs=source_refs,
                resources=resources,
                content_format=content_format,
            )
        )

    @tool
    def alcove_pin_list(
        workspace: str = "",
        home: str = "",
        tag: str | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        """List pinned personal notes."""
        return context.scoped_app(workspace, home).global_home.pin_list_payload(tag, status)

    @tool
    def alcove_pin_get(
        pin_id: str,
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Get a pinned personal note."""
        return context.scoped_app(workspace, home).global_home.pin_get_payload(pin_id)

    @tool
    def alcove_pin_search(
        query: str = "",
        workspace: str = "",
        home: str = "",
        kind: str = "",
        tag: str = "",
        status: str = "active",
    ) -> dict[str, Any]:
        """Discover candidate pins; inspect full pin content before nuanced answers."""
        return context.scoped_app(workspace, home).global_home.pin_search_payload(
            query=query,
            kind=kind,
            tag=tag,
            status=status,
        )

    @tool
    def alcove_pin_update(
        pin_id: str,
        workspace: str = "",
        home: str = "",
        title: str | None = None,
        description: str | None = None,
        summary: str | None = None,
        content: str | None = None,
        kind: str | None = None,
        tags: list[str] | None = None,
        priority: str | None = None,
        source_refs: list[str] | None = None,
        resources: list[str] | None = None,
        status: str | None = None,
        content_format: str | None = None,
    ) -> dict[str, Any]:
        """Update a pinned personal note through the governed global write path."""
        return context.scoped_app(workspace, home).global_home.pin_update_payload(
            pin_update_request(
                pin_id=pin_id,
                title=title,
                description=description,
                summary=summary,
                content=content,
                kind=kind,
                tags=tags,
                priority=priority,
                source_refs=source_refs,
                resources=resources,
                status=status,
                content_format=content_format,
            )
        )

    @tool
    def alcove_pin_rebuild_index(
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Rebuild the pins index."""
        return context.scoped_app(workspace, home).global_home.pin_rebuild_index_payload()

    @tool
    def alcove_pin_render_html(
        workspace: str = "",
        home: str = "",
        output_path: str = "",
    ) -> dict[str, Any]:
        """Render the pins HTML board."""
        return context.scoped_app(workspace, home).global_home.pin_render_html_payload(output_path)

    @tool
    def alcove_pin_archive(
        pin_id: str,
        workspace: str = "",
        home: str = "",
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Archive or preview archiving a pin."""
        return context.scoped_app(workspace, home).global_home.pin_archive_payload(pin_id, confirm)

    @tool
    def alcove_project_add(
        alias: str,
        path: str,
        workspace: str = "",
        home: str = "",
        note: str = "",
    ) -> dict[str, Any]:
        """Create or update a global project alias."""
        return context.scoped_app(workspace, home).global_home.project_add_payload(
            project_add_request(alias=alias, path=path, note=note)
        )

    @tool
    def alcove_project_get(
        alias: str,
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Get a global project alias."""
        return context.scoped_app(workspace, home).global_home.project_get_payload(alias)

    @tool
    def alcove_project_find(
        keyword: str,
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Find global project aliases or scanned root projects."""
        return context.scoped_app(workspace, home).global_home.project_find_payload(keyword)

    @tool
    def alcove_project_list(workspace: str = "", home: str = "") -> dict[str, Any]:
        """List global project aliases."""
        return context.scoped_app(workspace, home).global_home.project_list_payload()

    @tool
    def alcove_project_remove(
        alias: str,
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Remove a global project alias."""
        return context.scoped_app(workspace, home).global_home.project_remove_payload(alias)

    @tool
    def alcove_project_roots_set(
        roots: list[str],
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Configure roots scanned by project find."""
        return context.scoped_app(workspace, home).global_home.project_roots_set_payload(roots)

    @tool
    def alcove_okf_catalog_build(
        workspace: str = "",
        home: str = "",
        include_all_status: bool = False,
    ) -> dict[str, Any]:
        """Build the derived global OKF catalog used as a Markdown entry for AI-led reads."""
        return context.scoped_app(workspace, home).system.okf_catalog_build_payload(
            include_all_status=include_all_status
        )
