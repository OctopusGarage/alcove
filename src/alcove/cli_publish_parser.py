from __future__ import annotations

import argparse
from typing import Any


def add_publish_parser(sub: argparse._SubParsersAction[Any]) -> None:
    publish = sub.add_parser("publish", help="Publish Alcove module views to external targets")
    publish.add_argument("--home")
    publish_sub = publish.add_subparsers(dest="publish_command", required=True)

    publish_init = publish_sub.add_parser("init", help="Initialize a publisher definition")
    publish_init.add_argument("--home", default=argparse.SUPPRESS)
    publish_init.add_argument("publisher")
    publish_init.add_argument("--root-folder", default="iCloud/Alcove")
    publish_init.add_argument("--json", action="store_true")

    publish_list = publish_sub.add_parser("list", help="List publisher definitions")
    publish_list.add_argument("--home", default=argparse.SUPPRESS)
    publish_list.add_argument("--status", default="active")
    publish_list.add_argument("--json", action="store_true")

    publish_run = publish_sub.add_parser("run", help="Run a publisher")
    publish_run.add_argument("--home", default=argparse.SUPPRESS)
    publish_run.add_argument("publisher")
    publish_run.add_argument("--target", default="")
    publish_run.add_argument("--force", action="store_true")
    publish_run.add_argument("--json", action="store_true")
