from __future__ import annotations

from typing import Any

from alcove.mcp_context import McpInvocationContext
from alcove.mcp_resources import register_mcp_prompts, register_mcp_resources
from alcove.mcp_toolsets import resolve_mcp_toolset


class McpToolRegistrar:
    """Own MCP registration policy for toolsets, resources, and prompts."""

    def __init__(
        self,
        mcp: Any,
        *,
        canonical_toolset: str | None = None,
        enabled_tools: set[str] | None = None,
        default_workspace: str | None = None,
        default_home: str | None = None,
        toolset: str | None = None,
    ) -> None:
        self.mcp = mcp
        if canonical_toolset is None or enabled_tools is None:
            canonical_toolset, enabled_tools = resolve_mcp_toolset(toolset)
        self.canonical_toolset = canonical_toolset
        self.enabled_tools = enabled_tools
        self.context = McpInvocationContext(default_workspace, default_home)

    @classmethod
    def create(
        cls,
        mcp_cls: Any,
        *,
        default_workspace: str | None = None,
        default_home: str | None = None,
        toolset: str | None = None,
    ) -> "McpToolRegistrar":
        canonical_toolset, enabled_tools = resolve_mcp_toolset(toolset)
        return cls(
            mcp_cls(f"alcove-{canonical_toolset}"),
            canonical_toolset=canonical_toolset,
            enabled_tools=enabled_tools,
            default_workspace=default_workspace,
            default_home=default_home,
        )

    def register_shared_surfaces(self) -> None:
        register_mcp_resources(self.mcp, self.context)
        register_mcp_prompts(self.mcp, self.context)

    def tool(self, fn: Any) -> Any:
        if fn.__name__ in self.enabled_tools:
            return self.mcp.tool(fn)
        return fn
