from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from alcove.application import AlcoveApplication
from alcove.cli_io import print_install_result
from alcove.home import AlcoveHome, KnowledgeBaseRecord
from alcove.paths import compact_user_path
from alcove.profile_installer import ProfileInstaller


ArgumentError = Callable[[argparse.ArgumentParser, str], int]
RuntimeFactory = Callable[[Any], Any]


def handle_hub_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    argument_error: ArgumentError,
) -> int:
    profiles = ProfileInstaller(_home(args))
    if args.hub_command == "init":
        result = (
            profiles.hub_status(
                args.path,
                default_kb=args.default_kb,
                targets=args.target,
            )
            if args.status
            else profiles.hub_init(
                args.path,
                default_kb=args.default_kb,
                targets=args.target,
                link=args.link,
            )
        )
    elif args.hub_command == "install":
        result = (
            profiles.hub_status(
                args.path,
                default_kb=args.default_kb,
                targets=args.target,
            )
            if args.status
            else profiles.hub_install(
                args.path,
                default_kb=args.default_kb,
                targets=args.target,
                link=args.link,
            )
        )
    else:
        return argument_error(parser, "the following arguments are required: hub_command")
    return _print_profile_result(args, result)


def handle_global_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    runtime_from_args: RuntimeFactory,
    argument_error: ArgumentError,
) -> int:
    if args.global_command != "install":
        return argument_error(parser, "the following arguments are required: global_command")
    result = AlcoveApplication(runtime_from_args(args)).system.global_install_payload(
        args.target,
        status=args.status,
        uninstall=args.uninstall,
        dry_run=args.print_config,
        mcp_toolset=args.toolset,
        default_kb=args.default_kb,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.print_config and "configs" in result:
        for target, config in result["configs"].items():
            print(f"# {target}\n{config}")
    else:
        print_install_result(result)
    return 0


def handle_kb_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    argument_error: ArgumentError,
) -> int:
    home = _home(args)
    if args.kb_command == "add":
        record = home.register_knowledge_base(args.name, args.path)
        payload = {"status": "registered", "knowledge_base": kb_dict(record)}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"knowledge_base: {record.name} | {record.path}")
        return 0
    if args.kb_command == "list":
        records = [kb_dict(record) for record in home.list_knowledge_bases()]
        if args.json:
            print(json.dumps(records, ensure_ascii=False, indent=2))
        else:
            for record_dict in records:
                print(f"{record_dict['name']} | {record_dict['path']}")
        return 0
    if args.kb_command == "install":
        profiles = ProfileInstaller(home)
        result = (
            profiles.kb_status(
                args.name,
                targets=args.target,
            )
            if args.status
            else profiles.kb_install(
                args.name,
                targets=args.target,
                link=args.link,
            )
        )
        return _print_profile_result(args, result)
    return argument_error(parser, "the following arguments are required: kb_command")


def kb_dict(record: KnowledgeBaseRecord) -> dict[str, str]:
    return {
        "name": record.name,
        "path": compact_user_path(record.path),
        "config_path": compact_user_path(record.config_path),
    }


def _print_profile_result(args: Any, result: dict[str, Any]) -> int:
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_install_result(result)
    return 0


def _home(args: Any) -> AlcoveHome:
    return AlcoveHome.init(Path(args.home)) if getattr(args, "home", None) else AlcoveHome.init()
