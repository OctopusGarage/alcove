from __future__ import annotations

from typing import Any

from alcove.mcp_context import McpInvocationContext
from alcove.mcp_registrar import McpToolRegistrar
from alcove.radars import RadarModule


def register_mcp_radar_tools(
    registrar: McpToolRegistrar,
    context: McpInvocationContext,
) -> None:
    tool = registrar.tool

    @tool
    def alcove_radar_proposal_list(
        status: str = "", home: str = "", workspace: str = ""
    ) -> dict[str, Any]:
        """List governed radar action proposals and their lifecycle states."""
        app = context.scoped_app(workspace, home)
        return RadarModule(app.runtime.home).proposal_list(status)

    @tool
    def alcove_radar_proposal_get(
        proposal_id: str, home: str = "", workspace: str = ""
    ) -> dict[str, Any]:
        """Inspect one radar proposal, including its run and source provenance."""
        app = context.scoped_app(workspace, home)
        return RadarModule(app.runtime.home).proposal_get(proposal_id)

    @tool
    def alcove_radar_proposal_generate(
        radar_id: str,
        run_day: str = "",
        action_type: str = "idea",
        home: str = "",
        workspace: str = "",
    ) -> dict[str, Any]:
        """Extract proposals from an existing radar run without fetching or writing targets."""
        app = context.scoped_app(workspace, home)
        return RadarModule(app.runtime.home).proposal_generate(
            radar_id, run_day, action_type=action_type
        )

    @tool
    def alcove_radar_proposal_accept(
        proposal_id: str, home: str = "", workspace: str = ""
    ) -> dict[str, Any]:
        """Confirm a pending radar proposal through the existing task/idea/prompt write path."""
        return context.scoped_app(workspace, home).global_home.radar_proposal_accept_payload(
            proposal_id
        )

    @tool
    def alcove_radar_proposal_reject(
        proposal_id: str, home: str = "", workspace: str = ""
    ) -> dict[str, Any]:
        """Reject a pending radar proposal."""
        app = context.scoped_app(workspace, home)
        return RadarModule(app.runtime.home).proposal_resolve(proposal_id, "rejected")

    @tool
    def alcove_radar_proposal_defer(
        proposal_id: str, home: str = "", workspace: str = ""
    ) -> dict[str, Any]:
        """Defer a pending radar proposal for later review."""
        app = context.scoped_app(workspace, home)
        return RadarModule(app.runtime.home).proposal_resolve(proposal_id, "deferred")
