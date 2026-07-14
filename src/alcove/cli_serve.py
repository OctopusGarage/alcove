from __future__ import annotations

import argparse
from typing import Any, Callable

from alcove.dashboard_server import serve_dashboard
from alcove.home import AlcoveHome
from alcove.mcp_server import run_mcp_server


def handle_serve_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    workspace_from_args: Callable[[Any], Any],
    argument_error: Callable[[argparse.ArgumentParser, str], int],
) -> int:
    if args.mcp:
        workspace = workspace_from_args(args)
        workspace_arg = str(workspace.root) if workspace is not None else "."
        run_mcp_server(workspace_arg, args.home or None, toolset=args.toolset)
        return 0
    if args.dashboard:
        serve_dashboard(
            AlcoveHome.init(args.home or None),
            host=args.host,
            port=args.port,
        )
        return 0
    return argument_error(parser, "serve requires --mcp or --dashboard")
