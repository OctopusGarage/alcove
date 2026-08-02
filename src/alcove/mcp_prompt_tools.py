from __future__ import annotations

from typing import Any

from alcove.mcp_context import McpInvocationContext
from alcove.mcp_prompt_requests import prompt_request
from alcove.mcp_registrar import McpToolRegistrar


def register_mcp_prompt_tools(
    registrar: McpToolRegistrar,
    context: McpInvocationContext,
) -> None:
    tool = registrar.tool

    @tool
    def alcove_prompt_save(
        title: str = "",
        content: str = "",
        workspace: str = "",
        home: str = "",
        proposal_id: str = "",
        force: bool = False,
        description: str = "",
        tags: list[str] | None = None,
        use_cases: list[str] | None = None,
        source_refs: list[str] | None = None,
        kind: str = "full_prompt",
        domain: str = "",
        intent: str = "",
        surfaces: list[str] | None = None,
        triggers: list[str] | None = None,
        inputs: list[str] | None = None,
        outputs: list[str] | None = None,
    ) -> dict[str, Any]:
        """Save a reusable prompt from a proposal, or force an explicit direct write."""
        return context.scoped_app(workspace, home).global_home.prompt_save_payload(
            (
                prompt_request(
                    title=title,
                    content=content,
                    description=description,
                    tags=tags,
                    use_cases=use_cases,
                    source_refs=source_refs,
                    kind=kind,
                    domain=domain,
                    intent=intent,
                    surfaces=surfaces,
                    triggers=triggers,
                    inputs=inputs,
                    outputs=outputs,
                )
                if not proposal_id
                else None
            ),
            proposal_id=proposal_id,
            force=force,
        )

    @tool
    def alcove_prompt_propose(
        content: str,
        title: str = "",
        workspace: str = "",
        home: str = "",
        description: str = "",
        tags: list[str] | None = None,
        use_cases: list[str] | None = None,
        source_refs: list[str] | None = None,
        kind: str = "full_prompt",
        domain: str = "",
        intent: str = "",
        surfaces: list[str] | None = None,
        triggers: list[str] | None = None,
        inputs: list[str] | None = None,
        outputs: list[str] | None = None,
    ) -> dict[str, Any]:
        """Prepare, improve, deduplicate, and classify a prompt before saving."""
        return context.scoped_app(workspace, home).global_home.prompt_propose_payload(
            prompt_request(
                title=title,
                content=content,
                description=description,
                tags=tags,
                use_cases=use_cases,
                source_refs=source_refs,
                kind=kind,
                domain=domain,
                intent=intent,
                surfaces=surfaces,
                triggers=triggers,
                inputs=inputs,
                outputs=outputs,
            )
        )

    @tool
    def alcove_prompt_proposal(
        proposal_id: str,
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Read a saved prompt proposal before confirming the write."""
        return context.scoped_app(workspace, home).global_home.prompt_proposal_payload(proposal_id)

    @tool
    def alcove_prompt_search(
        query: str = "",
        workspace: str = "",
        home: str = "",
        tag: str = "",
        status: str = "active",
        kind: str = "",
        domain: str = "",
        surface: str = "",
    ) -> dict[str, Any]:
        """Discover candidate global prompts; inspect the full prompt before reuse."""
        return context.scoped_app(workspace, home).global_home.prompt_search_payload(
            query=query,
            tag=tag,
            status=status,
            kind=kind,
            domain=domain,
            surface=surface,
        )

    @tool
    def alcove_prompt_recommend(
        scenario: str,
        workspace: str = "",
        home: str = "",
        limit: int = 5,
        status: str = "active",
        surface: str = "",
    ) -> dict[str, Any]:
        """Recommend reusable prompts for a scenario; call get before copying full content."""
        return context.scoped_app(workspace, home).global_home.prompt_recommend_payload(
            scenario=scenario,
            limit=limit,
            status=status,
            surface=surface,
        )

    @tool
    def alcove_prompt_compose(
        scenario: str,
        workspace: str = "",
        home: str = "",
        limit: int = 4,
        status: str = "active",
        surface: str = "",
        max_chars_per_prompt: int = 1800,
    ) -> dict[str, Any]:
        """Compose a ready-to-use prompt pack from matching reusable prompt records."""
        return context.scoped_app(workspace, home).global_home.prompt_compose_payload(
            scenario=scenario,
            limit=limit,
            status=status,
            surface=surface,
            max_chars_per_prompt=max_chars_per_prompt,
        )

    @tool
    def alcove_prompt_audit(
        workspace: str = "",
        home: str = "",
        status: str = "active",
    ) -> dict[str, Any]:
        """Audit reusable prompt quality, metadata completeness, and duplicate risks."""
        return context.scoped_app(workspace, home).global_home.prompt_audit_payload(status=status)

    @tool
    def alcove_prompt_get(
        prompt_id: str,
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Get a reusable global prompt."""
        return context.scoped_app(workspace, home).global_home.prompt_get_payload(prompt_id)

    @tool
    def alcove_prompt_archive(
        prompt_id: str,
        workspace: str = "",
        home: str = "",
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Archive or preview archiving a reusable global prompt."""
        return context.scoped_app(workspace, home).global_home.prompt_archive_payload(
            prompt_id,
            confirm,
        )

    @tool
    def alcove_prompt_tags(workspace: str = "", home: str = "") -> dict[str, Any]:
        """List reusable global prompt tags."""
        return context.scoped_app(workspace, home).global_home.prompt_tags_payload()

    @tool
    def alcove_prompt_rebuild_index(workspace: str = "", home: str = "") -> dict[str, Any]:
        """Rebuild the reusable global prompt index."""
        return context.scoped_app(workspace, home).global_home.prompt_rebuild_index_payload()
