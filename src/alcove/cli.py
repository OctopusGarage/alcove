from __future__ import annotations

import argparse
import json
from pathlib import Path

from alcove import __version__
from alcove.errors import AlcoveError
from alcove.workspace import Workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="alcove")
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init", help="Initialize an Alcove workspace")
    init.add_argument("path", nargs="?", default=".")

    status = sub.add_parser("status", help="Show workspace status")
    status.add_argument("path", nargs="?", default=".")
    status.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.version:
            print(f"alcove {__version__}")
            return 0
        if args.command == "init":
            workspace = Workspace.init(Path(args.path))
            print(f"Initialized Alcove workspace at {workspace.root}")
            return 0
        if args.command == "status":
            workspace = Workspace.discover(Path(args.path))
            status = workspace.status()
            if args.json:
                print(json.dumps(status, ensure_ascii=False, indent=2))
            else:
                print(f"Alcove workspace: {status['root']}")
            return 0
        parser.print_help()
        return 0
    except AlcoveError as exc:
        parser.exit(2, f"alcove: {exc}\n")
        return 2


def entrypoint() -> None:
    raise SystemExit(main())
