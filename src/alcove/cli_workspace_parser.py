from __future__ import annotations

import argparse
from typing import Any


def add_workspace_parser(sub: argparse._SubParsersAction[Any]) -> None:
    workspace_cmd = sub.add_parser("workspace", help="Manage Alcove agent workspaces")
    workspace_cmd.add_argument("--home")
    workspace_sub = workspace_cmd.add_subparsers(dest="workspace_command", required=True)

    workspace_init = workspace_sub.add_parser("init", help="Initialize an agent workspace")
    workspace_init.add_argument("workspace_id", nargs="?", default="hub")
    workspace_init.add_argument("--home", default=argparse.SUPPRESS)
    workspace_init.add_argument("--path", default="")
    workspace_init.add_argument("--default-kb", default="")
    workspace_init.add_argument("--name", default="")
    workspace_init.add_argument("--tag", action="append")
    workspace_init.add_argument("--module", action="append")
    workspace_init.add_argument("--context", default="")
    workspace_init.add_argument("--target", action="append")
    workspace_init.add_argument("--link", action="store_true")
    workspace_init.add_argument("--json", action="store_true")

    workspace_list = workspace_sub.add_parser("list", help="List agent workspaces")
    workspace_list.add_argument("--home", default=argparse.SUPPRESS)
    workspace_list.add_argument("--json", action="store_true")

    workspace_status = workspace_sub.add_parser("status", help="Show agent workspace status")
    workspace_status.add_argument("workspace_id", nargs="?", default="hub")
    workspace_status.add_argument("--home", default=argparse.SUPPRESS)
    workspace_status.add_argument("--json", action="store_true")

    workspace_install = workspace_sub.add_parser("install", help="Install agent workspace files")
    workspace_install.add_argument("workspace_id", nargs="?", default="hub")
    workspace_install.add_argument("--home", default=argparse.SUPPRESS)
    workspace_install.add_argument("--target", action="append")
    workspace_install.add_argument("--link", action="store_true")
    workspace_install.add_argument("--json", action="store_true")

    workspace_run = workspace_sub.add_parser("run", help="Run a prompt in an agent workspace")
    workspace_run.add_argument("workspace_id")
    workspace_run.add_argument("prompt", nargs="+")
    workspace_run.add_argument("--home", default=argparse.SUPPRESS)
    workspace_run.add_argument("--agent", choices=["codex", "claude"], default="codex")
    workspace_run.add_argument("--print-command", action="store_true")
    workspace_run.add_argument("--json", action="store_true")

    workspace_okf = workspace_sub.add_parser("okf", help="Manage workspace-local OKF knowledge")
    workspace_okf.add_argument("--home", default=argparse.SUPPRESS)
    workspace_okf_sub = workspace_okf.add_subparsers(dest="okf_command", required=True)

    workspace_okf_init = workspace_okf_sub.add_parser("init", help="Initialize workspace OKF")
    workspace_okf_init.add_argument("workspace_id")
    workspace_okf_init.add_argument("--home", default=argparse.SUPPRESS)
    workspace_okf_init.add_argument("--kb-name", default="")
    workspace_okf_init.add_argument("--json", action="store_true")

    workspace_okf_status = workspace_okf_sub.add_parser("status", help="Show workspace OKF status")
    workspace_okf_status.add_argument("workspace_id")
    workspace_okf_status.add_argument("--home", default=argparse.SUPPRESS)
    workspace_okf_status.add_argument("--json", action="store_true")

    workspace_okf_note = workspace_okf_sub.add_parser("add-note", help="Add a workspace OKF note")
    workspace_okf_note.add_argument("workspace_id")
    workspace_okf_note.add_argument("topic")
    workspace_okf_note.add_argument("title")
    workspace_okf_note.add_argument("--home", default=argparse.SUPPRESS)
    workspace_okf_note.add_argument("--summary", default="")
    workspace_okf_note.add_argument("--content", default="")
    workspace_okf_note.add_argument("--tag", action="append")
    workspace_okf_note.add_argument("--json", action="store_true")

    workspace_okf_import = workspace_okf_sub.add_parser(
        "import-file", help="Import a file into workspace OKF"
    )
    workspace_okf_import.add_argument("workspace_id")
    workspace_okf_import.add_argument("file")
    workspace_okf_import.add_argument("--home", default=argparse.SUPPRESS)
    workspace_okf_import.add_argument("--topic", default="")
    workspace_okf_import.add_argument("--title", default="")
    workspace_okf_import.add_argument("--tag", action="append")
    workspace_okf_import.add_argument("--no-copy", action="store_true")
    workspace_okf_import.add_argument("--json", action="store_true")

    workspace_okf_search = workspace_okf_sub.add_parser("search", help="Search workspace OKF")
    workspace_okf_search.add_argument("workspace_id")
    workspace_okf_search.add_argument("query")
    workspace_okf_search.add_argument("--home", default=argparse.SUPPRESS)
    workspace_okf_search.add_argument("--limit", type=int, default=20)
    workspace_okf_search.add_argument("--json", action="store_true")
