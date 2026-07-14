from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from alcove.application import AlcoveApplication
from alcove.cli_io import print_install_result
from alcove.home import AlcoveHome
from alcove.paths import compact_user_path
from alcove.workspace import Workspace


ArgumentError = Callable[[argparse.ArgumentParser, str], int]
RuntimeFactory = Callable[[Any], Any]


def handle_init_command(args: Any) -> int:
    workspace = Workspace.init(Path(args.path))
    print(f"Initialized Alcove workspace at {workspace.root}")
    return 0


def handle_status_command(args: Any) -> int:
    workspace = Workspace.discover(Path(args.path))
    status = workspace.status()
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print(f"Alcove workspace: {status['root']}")
    return 0


def handle_doctor_command(
    args: Any,
    *,
    runtime_from_args: RuntimeFactory,
) -> int:
    report = AlcoveApplication(runtime_from_args(args)).system.doctor_payload()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for check in report["checks"]:
            print(f"{check['status']} | {check['name']} | {check.get('message', '')}")
    return 1 if report["status"] == "issues" else 0


def handle_health_command(
    args: Any,
    *,
    runtime_from_args: RuntimeFactory,
) -> int:
    report = AlcoveApplication(runtime_from_args(args)).system.health_payload(
        fix=args.fix,
        strict=args.strict,
        deep=args.deep,
        refresh_stale_connectors=args.refresh_stale_connectors,
        refresh_all_connectors=args.refresh_all_connectors,
        fixture_context=args.fixture_context,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"status: {report['status']}")
        for issue in report["issues"]:
            print(
                f"{issue['severity']} | {issue['module']} | "
                f"{issue['kind']} | {issue['path']} | {issue['message']}"
            )
        for action in report["actions"]:
            print(f"action | {action['module']} | {action['action']} | {action['path']}")
    return 1 if report["status"] == "issues" else 0


def handle_install_command(
    args: Any,
    *,
    runtime_from_args: RuntimeFactory,
) -> int:
    result = AlcoveApplication(runtime_from_args(args)).system.install_payload(
        args.target,
        status=args.status,
        uninstall=args.uninstall,
        dry_run=args.print_config,
        mcp_toolset=args.toolset,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.print_config and "configs" in result:
        for target, config in result["configs"].items():
            print(f"# {target}\n{config}")
    else:
        print_install_result(result)
    return 0


def handle_home_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    argument_error: ArgumentError,
) -> int:
    if args.home_command != "init":
        return argument_error(parser, "the following arguments are required: home_command")
    home = AlcoveHome.init(Path(args.home)) if args.home else AlcoveHome.init()
    payload = {
        "status": "initialized",
        "home": compact_user_path(home.root),
        "paths": {
            "config": compact_user_path(home.paths().config),
            "knowledge_bases": compact_user_path(home.paths().knowledge_bases),
            "projects": compact_user_path(home.paths().projects),
            "prompts": compact_user_path(home.paths().prompts),
            "pins": compact_user_path(home.paths().pins),
            "tasks": compact_user_path(home.paths().tasks),
            "mounts": compact_user_path(home.paths().mounts),
            "connectors": compact_user_path(home.paths().connectors),
            "stats": compact_user_path(home.paths().stats),
        },
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Alcove home: {home.root}")
    return 0


def handle_okf_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    runtime_from_args: Callable[..., Any],
    argument_error: ArgumentError,
) -> int:
    app = AlcoveApplication(runtime_from_args(args))
    if args.okf_command == "catalog" and args.okf_catalog_command == "build":
        payload = app.system.okf_catalog_build_payload(include_all_status=args.include_all_status)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"okf catalog: {payload['root']} | files: {len(payload['files'])}")
        return 0
    return argument_error(parser, "the following arguments are required: okf_command")


def handle_validate_command(
    args: Any,
    *,
    runtime_from_args: RuntimeFactory,
) -> int:
    issues = AlcoveApplication(runtime_from_args(args)).system.validate_payload(
        strict_quality=args.strict_quality
    )["issues"]
    if args.json:
        print(json.dumps({"issues": issues}, ensure_ascii=False, indent=2))
    else:
        for issue in issues:
            print(f"{issue['kind']} | {issue['path']} | {issue['message']}")
    return 1 if issues else 0


def handle_gardener_command(
    args: Any,
    *,
    runtime_from_args: RuntimeFactory,
) -> int:
    payload = AlcoveApplication(runtime_from_args(args)).system.gardener_payload(prune=args.prune)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for issue in payload["issues"]:
            print(f"{issue['kind']} | {issue['path']} | {issue['message']}")
        for action in payload["actions"]:
            print(f"{action['action']} | {action['path']}")
    return 0
