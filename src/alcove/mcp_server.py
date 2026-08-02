from __future__ import annotations

from typing import Any

from alcove.mcp_context import agent_payload as _agent_payload
from alcove.mcp_external_tools import register_mcp_external_tools
from alcove.mcp_global_tools import register_mcp_global_tools
from alcove.mcp_managed_kb_tools import register_mcp_managed_kb_tools
from alcove.mcp_planner_tools import register_mcp_planner_tools
from alcove.mcp_registrar import McpToolRegistrar
from alcove.mcp_search_requests import search_request

from alcove.mcp_direct_tools import (
    command_hints_tool,
    gardener_tool,
    get_topic_tool,
    idea_archive_tool,
    idea_edit_tool,
    idea_promote_routine_tool,
    idea_promote_tool,
    inbox_peek_tool,
    link_source_tool,
    mount_list_tool,
    note_source_tool,
    okf_catalog_build_tool,
    pin_add_tool,
    pin_get_tool,
    pin_rebuild_index_tool,
    pin_render_html_tool,
    pin_search_tool,
    pin_update_tool,
    project_add_tool,
    project_find_tool,
    prompt_get_tool,
    prompt_rebuild_index_tool,
    prompt_save_tool,
    revise_knowledge_tool,
    routine_add_tool,
    routine_archive_tool,
    routine_list_tool,
    routine_materialize_due_tool,
    routine_pause_tool,
    routine_resume_tool,
    search_tool,
    task_add_tool,
    task_digest_tool,
    task_edit_tool,
    task_list_tool,
)

__all__ = [
    "command_hints_tool",
    "create_mcp_server",
    "gardener_tool",
    "get_topic_tool",
    "idea_archive_tool",
    "idea_edit_tool",
    "idea_promote_routine_tool",
    "idea_promote_tool",
    "inbox_peek_tool",
    "link_source_tool",
    "mount_list_tool",
    "note_source_tool",
    "okf_catalog_build_tool",
    "pin_add_tool",
    "pin_get_tool",
    "pin_rebuild_index_tool",
    "pin_render_html_tool",
    "pin_search_tool",
    "pin_update_tool",
    "project_add_tool",
    "project_find_tool",
    "prompt_get_tool",
    "prompt_rebuild_index_tool",
    "prompt_save_tool",
    "revise_knowledge_tool",
    "routine_add_tool",
    "routine_archive_tool",
    "routine_list_tool",
    "routine_materialize_due_tool",
    "routine_pause_tool",
    "routine_resume_tool",
    "run_mcp_server",
    "search_tool",
    "task_add_tool",
    "task_digest_tool",
    "task_edit_tool",
    "task_list_tool",
]


def create_mcp_server(
    default_workspace: str | None = None,
    default_home: str | None = None,
    toolset: str | None = None,
) -> Any:
    from fastmcp import FastMCP

    registrar = McpToolRegistrar.create(
        FastMCP,
        default_workspace=default_workspace,
        default_home=default_home,
        toolset=toolset,
    )
    mcp = registrar.mcp
    context = registrar.context
    tool = registrar.tool
    registrar.register_shared_surfaces()
    register_mcp_external_tools(registrar, context)
    register_mcp_global_tools(registrar, context)
    register_mcp_managed_kb_tools(registrar, context)
    register_mcp_planner_tools(registrar, context)

    @tool
    def alcove_command_hints(
        workspace: str = "",
        home: str = "",
        workflow: str = "",
    ) -> dict[str, Any]:
        """Discover CLI commands for complex Alcove workflows kept outside MCP."""
        effective_home = context.effective_home(home)
        effective_workspace = context.effective_workspace(workspace, home=effective_home)
        return command_hints_tool(
            workspace=effective_workspace,
            home=effective_home,
            workflow=workflow,
        )

    @tool
    def alcove_search(
        query: str = "",
        workspace: str = "",
        home: str = "",
        type_filter: str | None = None,
        tag: str | None = None,
        topic: str | None = None,
        platform: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        min_confidence: float | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Discover candidate Alcove records; treat results as leads, not final truth.

        For broad or ambiguous questions, inspect returned OKF paths, source refs,
        mount refs, connector items, and local files before answering.
        """
        return _agent_payload(
            context.scoped_app(workspace, home).search.search_payload(
                search_request(
                    query=query,
                    type_filter=type_filter,
                    tag=tag,
                    topic=topic,
                    platform=platform,
                    date_from=date_from,
                    date_to=date_to,
                    min_confidence=min_confidence,
                    status=status,
                    limit=limit,
                ),
                surface="mcp",
            )
        )

    return mcp


def run_mcp_server(
    default_workspace: str | None = None,
    default_home: str | None = None,
    toolset: str | None = None,
) -> None:
    create_mcp_server(default_workspace, default_home, toolset=toolset).run()
