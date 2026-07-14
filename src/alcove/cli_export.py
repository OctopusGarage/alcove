from __future__ import annotations

import argparse
import json
from typing import Any, Callable

from alcove.application import AlcoveApplication


def handle_export_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    runtime_from_args: Callable[[Any], Any],
    argument_error: Callable[[argparse.ArgumentParser, str], int],
) -> int:
    runtime = runtime_from_args(args)
    app = AlcoveApplication(runtime)
    if args.export_command == "global":
        return _print_export(
            app.system.export_global_payload(args.output_dir), json_output=args.json
        )
    if args.export_command == "kb":
        return _print_export(
            app.system.export_kb_payload(args.name, args.output_dir),
            json_output=args.json,
        )
    if args.export_command == "all":
        return _print_export(app.system.export_all_payload(args.output_dir), json_output=args.json)
    return argument_error(parser, "the following arguments are required: export_command")


def _print_export(result: dict[str, Any], *, json_output: bool) -> int:
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"exported: {result['output_dir']}")
    return 0
