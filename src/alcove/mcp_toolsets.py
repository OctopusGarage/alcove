from __future__ import annotations

from typing import Final

from alcove.entry_policy import default_toolset_for_entry

MCP_TOOL_INVENTORY: Final[dict[str, tuple[str, ...]]] = {
    "guidance": ("alcove_command_hints",),
    "search": ("alcove_search",),
    "inbox": (
        "alcove_inbox_peek",
        "alcove_inbox_read",
        "alcove_inbox_manual_add",
        "alcove_inbox_archive",
        "alcove_inbox_note",
        "alcove_inbox_todo",
        "alcove_inbox_delete",
    ),
    "knowledge": (
        "alcove_note_source",
        "alcove_get_topic",
        "alcove_link_source",
        "alcove_knowledge_add_note",
        "alcove_knowledge_revise",
        "alcove_knowledge_add_question",
        "alcove_knowledge_add_entity",
        "alcove_knowledge_promote",
        "alcove_knowledge_refresh",
        "alcove_knowledge_delete",
        "alcove_knowledge_topics",
    ),
    "global_memory": (
        "alcove_pin_add",
        "alcove_pin_list",
        "alcove_pin_get",
        "alcove_pin_search",
        "alcove_pin_update",
        "alcove_pin_rebuild_index",
        "alcove_pin_render_html",
        "alcove_pin_archive",
        "alcove_prompt_save",
        "alcove_prompt_search",
        "alcove_prompt_get",
        "alcove_prompt_archive",
        "alcove_prompt_tags",
        "alcove_prompt_rebuild_index",
        "alcove_okf_catalog_build",
        "alcove_project_add",
        "alcove_project_get",
        "alcove_project_find",
        "alcove_project_list",
        "alcove_project_remove",
        "alcove_project_roots_set",
    ),
    "planner": (
        "alcove_task_add",
        "alcove_task_list",
        "alcove_task_edit",
        "alcove_task_complete",
        "alcove_task_cancel",
        "alcove_task_digest",
        "alcove_idea_add",
        "alcove_idea_list",
        "alcove_idea_edit",
        "alcove_idea_archive",
        "alcove_idea_promote",
        "alcove_idea_promote_routine",
        "alcove_routine_add",
        "alcove_routine_list",
        "alcove_routine_materialize_due",
        "alcove_routine_pause",
        "alcove_routine_resume",
        "alcove_routine_archive",
    ),
    "external_indexes": (
        "alcove_mount_list",
        "alcove_mount_add",
        "alcove_mount_scan",
        "alcove_connector_fetch",
        "alcove_connector_status",
        "alcove_connector_refresh",
        "alcove_connector_apple_notes_index",
        "alcove_connector_apple_notes_import_local",
        "alcove_connector_github_stars_index",
        "alcove_connector_github_stars_import_url",
        "alcove_connector_chrome_bookmarks_index",
        "alcove_connector_chrome_bookmarks_import_local",
    ),
    "health_export": (
        "alcove_health",
        "alcove_gardener",
        "alcove_doctor",
        "alcove_validate",
        "alcove_export_global",
        "alcove_export_kb",
        "alcove_export_all",
    ),
}

MCP_TOOLSET_ALIASES: Final[dict[str, str]] = {
    "admin": "full",
    "all": "full",
}


def mcp_tool_inventory() -> dict[str, list[str]]:
    return {module: list(tools) for module, tools in MCP_TOOL_INVENTORY.items()}


def all_mcp_tools() -> set[str]:
    return {tool for tools in MCP_TOOL_INVENTORY.values() for tool in tools}


def resolve_mcp_toolset(toolset: str | None) -> tuple[str, set[str]]:
    normalized = (toolset or "").strip().lower()
    canonical = MCP_TOOLSET_ALIASES.get(normalized)
    if canonical is None:
        try:
            canonical = default_toolset_for_entry(normalized)
        except ValueError:
            canonical = None
    if canonical is None:
        choices = ", ".join(
            sorted(
                [
                    *MCP_TOOLSET_ALIASES,
                    "full",
                    "global",
                    "global-lite",
                    "hub",
                    "hub-full",
                    "kb",
                    "knowledge-base",
                    "lite",
                ]
            )
        )
        raise ValueError(f"Unknown MCP toolset: {toolset}. Expected one of: {choices}")
    if canonical == "full":
        return canonical, all_mcp_tools()
    if canonical == "kb":
        return canonical, _kb_tools()
    if canonical == "lite":
        return canonical, _lite_tools()
    raise ValueError(f"Unsupported MCP toolset: {canonical}")


def _lite_tools() -> set[str]:
    return {
        "alcove_command_hints",
        "alcove_search",
        "alcove_pin_add",
        "alcove_pin_list",
        "alcove_pin_get",
        "alcove_pin_search",
        "alcove_pin_update",
        "alcove_prompt_save",
        "alcove_prompt_search",
        "alcove_prompt_get",
        "alcove_task_add",
        "alcove_task_list",
        "alcove_task_edit",
        "alcove_task_complete",
        "alcove_task_cancel",
        "alcove_idea_add",
        "alcove_idea_list",
        "alcove_idea_edit",
        "alcove_idea_archive",
        "alcove_idea_promote",
        "alcove_inbox_manual_add",
        "alcove_health",
    }


def _kb_tools() -> set[str]:
    return {
        "alcove_command_hints",
        "alcove_search",
        "alcove_inbox_peek",
        "alcove_inbox_read",
        "alcove_inbox_manual_add",
        "alcove_inbox_archive",
        "alcove_inbox_note",
        "alcove_inbox_todo",
        "alcove_inbox_delete",
        "alcove_note_source",
        "alcove_get_topic",
        "alcove_knowledge_add_note",
        "alcove_knowledge_revise",
        "alcove_knowledge_add_question",
        "alcove_knowledge_add_entity",
        "alcove_knowledge_promote",
        "alcove_knowledge_refresh",
        "alcove_knowledge_delete",
        "alcove_knowledge_topics",
        "alcove_link_source",
        "alcove_pin_add",
        "alcove_pin_search",
        "alcove_pin_get",
        "alcove_task_add",
        "alcove_task_list",
        "alcove_task_edit",
        "alcove_idea_add",
        "alcove_idea_list",
        "alcove_idea_edit",
        "alcove_idea_archive",
        "alcove_doctor",
        "alcove_validate",
        "alcove_health",
    }
