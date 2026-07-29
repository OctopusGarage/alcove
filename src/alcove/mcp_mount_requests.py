from alcove.mounts import AddMountRequest, MountIndexPolicy


def mount_index_policy_request(
    *,
    profile: str = "raw",
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    max_file_size_kb: int = 976,
) -> MountIndexPolicy:
    """Build a mount index policy request shared by MCP adapter surfaces."""
    return MountIndexPolicy(
        profile=profile,
        include=include or [],
        exclude=exclude or [],
        max_file_size_kb=max_file_size_kb,
    )


def mount_add_request(
    *,
    path: str,
    name: str = "",
    mount_type: str = "local-folder",
    tags: list[str] | None = None,
    profile: str = "raw",
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    max_file_size_kb: int = 976,
) -> AddMountRequest:
    """Build an add-mount request shared by MCP adapter surfaces."""
    return AddMountRequest(
        path=path,
        name=name,
        mount_type=mount_type,
        tags=tags or [],
        index_policy=mount_index_policy_request(
            profile=profile,
            include=include,
            exclude=exclude,
            max_file_size_kb=max_file_size_kb,
        ),
    )
