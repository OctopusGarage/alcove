from __future__ import annotations

from typing import Any

from alcove.mcp_context import McpInvocationContext
from alcove.mcp_registrar import McpToolRegistrar
from alcove.pins import AddPinRequest, UpdatePinRequest
from alcove.projects import AddProjectRequest
from alcove.prompts import AddPromptRequest


def register_mcp_global_tools(
    registrar: McpToolRegistrar,
    context: McpInvocationContext,
) -> None:
    tool = registrar.tool

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
            AddPinRequest(
                title=title,
                description=description,
                summary=summary,
                content=content,
                kind=kind,
                tags=tags or [],
                priority=priority,
                source_refs=source_refs or [],
                resources=resources or [],
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
            UpdatePinRequest(
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
            AddProjectRequest(alias=alias, path=path, note=note)
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
                AddPromptRequest(
                    title=title,
                    content=content,
                    description=description,
                    tags=tags or [],
                    use_cases=use_cases or [],
                    source_refs=source_refs or [],
                    kind=kind,
                    domain=domain,
                    intent=intent,
                    surfaces=surfaces or [],
                    triggers=triggers or [],
                    inputs=inputs or [],
                    outputs=outputs or [],
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
            AddPromptRequest(
                title=title,
                content=content,
                description=description,
                tags=tags or [],
                use_cases=use_cases or [],
                source_refs=source_refs or [],
                kind=kind,
                domain=domain,
                intent=intent,
                surfaces=surfaces or [],
                triggers=triggers or [],
                inputs=inputs or [],
                outputs=outputs or [],
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
