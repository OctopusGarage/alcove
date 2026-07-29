from __future__ import annotations

from alcove.projects import AddProjectRequest


def project_add_request(
    *,
    alias: str,
    path: str,
    note: str = "",
) -> AddProjectRequest:
    """Build the project write request shared by MCP adapter surfaces."""
    return AddProjectRequest(alias=alias, path=path, note=note)
