from __future__ import annotations

import argparse
import json
from typing import Any, Callable

from alcove.dashboard import DashboardModule
from alcove.home import AlcoveHome


ArgumentError = Callable[[argparse.ArgumentParser, str], int]


def handle_dashboard_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    argument_error: ArgumentError,
) -> int:
    module = DashboardModule(home=AlcoveHome.init(args.home or None))
    if args.dashboard_command == "build":
        result = module.build(
            args.output or None,
            build_frontend=not args.skip_frontend_build,
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"dashboard: {result['index']}")
        return 0
    if args.dashboard_command == "import-pins":
        result = module.import_pins(
            regular_file=args.regular_file or None,
            todo_file=args.todo_file or None,
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            for kind, payload in result.items():
                if isinstance(payload, dict) and "imported" in payload:
                    print(f"{kind}: {payload['imported']} pins")
                else:
                    print(f"{kind}: {payload}")
        return 0
    return argument_error(parser, "the following arguments are required: dashboard_command")
