from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from alcove.automations import AutomationsModule
from alcove.blog_monitor import BlogMonitorModule
from alcove.home import AlcoveHome
from alcove.publishers import PublisherModule
from alcove.radars import RadarModule
from alcove.watchers import WatcherModule


TagReader = Callable[[Any], list[str]]
ArgumentError = Callable[[argparse.ArgumentParser, str], int]


def handle_automation_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    argument_error: ArgumentError,
) -> int:
    home = _home(args)
    automations = AutomationsModule(home)
    if args.automation_command == "list":
        payload = automations.list_jobs(status=args.status)
    elif args.automation_command == "run":
        payload = automations.run(args.job_id, allow_agent=args.allow_agent)
    elif args.automation_command == "run-due":
        payload = automations.run_due(allow_agent=args.allow_agent)
    elif args.automation_command == "add-shell":
        payload = automations.add_shell(
            name=args.name,
            command=args.cmd,
            cwd=args.cwd,
            ttl_hours=args.ttl_hours,
            timeout_seconds=args.timeout_seconds,
            notify=args.notify,
        )
    elif args.automation_command == "add-git-sync":
        payload = automations.add_git_sync(
            name=args.name,
            repo_path=args.repo_path,
            commit_message=args.commit_message,
            ttl_hours=args.ttl_hours,
            timeout_seconds=args.timeout_seconds,
            notify=args.notify,
        )
    else:
        return argument_error(parser, "the following arguments are required: automation_command")
    return _print_json(payload)


def handle_publish_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    argument_error: ArgumentError,
) -> int:
    publishers = PublisherModule(_home(args))
    if args.publish_command == "init":
        if args.publisher != "apple-notes":
            return argument_error(parser, "supported publisher: apple-notes")
        payload = publishers.init_apple_notes(root_folder=args.root_folder)
    elif args.publish_command == "list":
        payload = publishers.list(status=args.status)
    elif args.publish_command == "run":
        payload = publishers.run(
            args.publisher,
            target_id=args.target,
            force=args.force,
        )
    else:
        return argument_error(parser, "the following arguments are required: publish_command")
    return _print_json(payload)


def handle_watch_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    tags_from_args: TagReader,
    argument_error: ArgumentError,
) -> int:
    watcher_module = WatcherModule(_home(args))
    if args.watch_command == "add":
        payload = watcher_module.add(
            title=args.title,
            url=args.url,
            kind=args.kind,
            kb=args.kb,
            tags=tags_from_args(args),
            ttl_hours=args.ttl_hours,
        )
    elif args.watch_command == "list":
        payload = watcher_module.list_sources(status=args.status)
    elif args.watch_command == "check":
        payload = watcher_module.check(source_id=args.source_id, stale_only=args.stale)
    else:
        return argument_error(parser, "the following arguments are required: watch_command")
    return _print_json(payload)


def handle_blog_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    tags_from_args: TagReader,
    argument_error: ArgumentError,
) -> int:
    blog_module = BlogMonitorModule(_home(args))
    if args.blog_command == "add":
        payload = blog_module.add(
            name=args.name,
            url=args.url,
            source_id=args.source_id,
            discover_method=args.discover,
            link_pattern=args.link_pattern,
            days_back=args.days_back,
            capture_enabled=args.capture,
            capture_adapter=args.adapter,
            kb=args.kb,
            inbox_path=args.inbox_path,
            summary_enabled=args.summary,
            notify_enabled=args.notify,
            tags=tags_from_args(args),
            ttl_hours=args.ttl_hours,
        )
    elif args.blog_command == "list":
        payload = blog_module.list_sources(status=args.status)
    elif args.blog_command == "seed":
        payload = blog_module.seed(source_id=args.source_id)
    elif args.blog_command == "check":
        payload = blog_module.check(
            source_id=args.source_id,
            stale_only=args.stale,
            capture_override=False if args.no_capture else None,
            summary_override=True if args.summary else None,
            notify_override=True if args.notify else None,
        )
    else:
        return argument_error(parser, "the following arguments are required: blog_command")
    return _print_json(payload)


def handle_radar_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    argument_error: ArgumentError,
) -> int:
    radar_module = RadarModule(_home(args))
    if args.radar_command == "list":
        payload = radar_module.list(status=args.status)
    elif args.radar_command == "init":
        if not args.from_preset:
            return argument_error(
                parser, "--from-preset is required for radar init in this release"
            )
        payload = radar_module.init_from_preset(args.from_preset, args.radar_id, force=args.force)
    elif args.radar_command == "run":
        payload = radar_module.run(
            args.radar_id,
            skip_fetch=args.skip_fetch,
            force=args.force,
            ai=args.ai,
            notify=args.notify,
        )
    elif args.radar_command == "status":
        payload = radar_module.status(args.radar_id)
    elif args.radar_command == "preset":
        if args.radar_preset_command != "list":
            return argument_error(
                parser,
                "the following arguments are required: radar_preset_command",
            )
        payload = radar_module.preset_list()
    else:
        return argument_error(parser, "the following arguments are required: radar_command")
    return _print_json(payload)


def _home(args: Any) -> AlcoveHome:
    return AlcoveHome.init(Path(args.home)) if getattr(args, "home", None) else AlcoveHome.init()


def _print_json(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0
