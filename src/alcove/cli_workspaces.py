from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from alcove.agent_workspaces import AgentWorkspacesModule
from alcove.home import AlcoveHome


def handle_workspace_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    argument_error: Callable[[argparse.ArgumentParser, str], int],
) -> int:
    module = AgentWorkspacesModule(_home(args))
    if args.workspace_command == "init":
        result = module.init(
            args.workspace_id,
            path=args.path,
            default_kb=args.default_kb,
            name=args.name,
            tags=args.tag or [],
            modules=args.module or [],
            context=args.context,
            targets=args.target,
            link=args.link,
        )
        return _print(args, result)
    if args.workspace_command == "install":
        result = module.install(
            args.workspace_id,
            targets=args.target,
            link=args.link,
        )
        return _print(args, result)
    if args.workspace_command == "status":
        return _print(args, module.status(args.workspace_id))
    if args.workspace_command == "list":
        records = [record.as_dict() for record in module.list()]
        return _print(args, records)
    if args.workspace_command == "run":
        prompt = " ".join(args.prompt).strip()
        if not prompt:
            return argument_error(parser, "workspace run requires a prompt")
        result = module.run_command(
            args.workspace_id,
            agent=args.agent,
            prompt=prompt,
            print_command=args.print_command,
        )
        return _print(args, result)
    if args.workspace_command == "okf":
        if args.okf_command == "init":
            return _print(args, module.okf_init(args.workspace_id, kb_name=args.kb_name))
        if args.okf_command == "status":
            return _print(args, module.okf_status(args.workspace_id))
        if args.okf_command == "add-note":
            summary = args.summary or args.content
            if not summary:
                return argument_error(
                    parser, "workspace okf add-note requires --summary or --content"
                )
            return _print(
                args,
                module.okf_add_note(
                    args.workspace_id,
                    topic=args.topic,
                    title=args.title,
                    summary=summary,
                    tags=args.tag or [],
                ),
            )
        if args.okf_command == "import-file":
            return _print(
                args,
                module.okf_import_file(
                    args.workspace_id,
                    file_path=args.file,
                    topic=args.topic,
                    title=args.title,
                    tags=args.tag or [],
                    copy=not args.no_copy,
                ),
            )
        if args.okf_command == "search":
            return _print(
                args,
                module.okf_search(args.workspace_id, query=args.query, limit=args.limit),
            )
    return argument_error(parser, "the following arguments are required: workspace_command")


def _print(args: Any, payload: Any) -> int:
    if bool(getattr(args, "json", False)):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if isinstance(payload, list):
        for item in payload:
            print(f"{item['id']} | {item['profile']} | {item['path']}")
        return 0
    if isinstance(payload, dict) and "workspace" in payload:
        workspace = payload["workspace"]
        print(f"workspace: {workspace['id']}")
        print(f"profile: {workspace['profile']}")
        print(f"path: {workspace['path']}")
        if payload.get("okf"):
            print(f"okf: {payload['okf']['root']}")
        if payload.get("registry"):
            print(f"registry: {payload['registry']}")
        if payload.get("command"):
            print("command:")
            print(" ".join(str(part) for part in payload["command"]))
        for item in payload.get("files", []):
            print(f"{item.get('action', 'status')}: {item['path']}")
        return 0
    print(payload)
    return 0


def _home(args: Any) -> AlcoveHome:
    return AlcoveHome.init(Path(args.home)) if getattr(args, "home", None) else AlcoveHome.init()
