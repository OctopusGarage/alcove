from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from alcove.cli_dashboard import handle_dashboard_command
from alcove.cli_export import handle_export_command
from alcove.cli_external import (
    handle_connector_command,
    handle_link_command,
    handle_mount_command,
)
from alcove.cli_global_home import handle_pin_command, handle_project_command
from alcove.cli_managed_kb import handle_inbox_command, handle_knowledge_command
from alcove.cli_operations import (
    handle_automation_command,
    handle_blog_command,
    handle_publish_command,
    handle_radar_command,
    handle_watch_command,
)
from alcove.cli_planner import handle_idea_command, handle_task_command
from alcove.cli_profiles import (
    handle_global_command,
    handle_hub_command,
    handle_kb_command,
)
from alcove.cli_prompts import handle_prompt_command
from alcove.cli_search import handle_search_command
from alcove.cli_serve import handle_serve_command
from alcove.cli_service import handle_service_command
from alcove.cli_system import (
    handle_doctor_command,
    handle_gardener_command,
    handle_health_command,
    handle_home_command,
    handle_init_command,
    handle_install_command,
    handle_okf_command,
    handle_status_command,
    handle_validate_command,
)
from alcove.cli_usage import handle_usage_command
from alcove.runtime import AlcoveRuntime
from alcove.workspace import Workspace


ArgumentError = Callable[[argparse.ArgumentParser, str], int]
RuntimeFactory = Callable[[argparse.Namespace], AlcoveRuntime]
WorkspaceFactory = Callable[[argparse.Namespace], Workspace]
TagReader = Callable[[argparse.Namespace], list[str]]
OptionalTagReader = Callable[[argparse.Namespace], list[str] | None]
StringListReader = Callable[[argparse.Namespace], list[str]]
OptionalStringListReader = Callable[[argparse.Namespace], list[str] | None]
TakeawayReader = Callable[[str], list[str]]
CsvSplitter = Callable[[str], list[str]]
ScheduleReader = Callable[..., dict[str, Any]]
InboxPrinter = Callable[[dict[str, Any]], None]
PathPrinter = Callable[[str, Path | None], None]
SearchRowsPrinter = Callable[[list[dict[str, Any]]], None]
CommandHandler = Callable[[argparse.Namespace, "CliDispatchContext"], int]


@dataclass(frozen=True)
class CliDispatchContext:
    parser: argparse.ArgumentParser
    runtime_from_args: RuntimeFactory
    workspace_runtime_from_args: RuntimeFactory
    health_runtime_from_args: RuntimeFactory
    workspace_from_args: WorkspaceFactory
    tags_from_args: TagReader
    optional_tags_from_args: OptionalTagReader
    refs_from_args: StringListReader
    optional_refs_from_args: OptionalStringListReader
    resources_from_args: StringListReader
    optional_resources_from_args: OptionalStringListReader
    selected_takeaways_from_args: TakeawayReader
    routine_schedule_from_args: ScheduleReader
    split_csv_values: CsvSplitter
    print_inbox_post: InboxPrinter
    print_path: PathPrinter
    print_search_rows: SearchRowsPrinter
    argument_error: ArgumentError


def dispatch_cli_command(args: argparse.Namespace, context: CliDispatchContext) -> int:
    """Dispatch a parsed CLI command through one registry-backed seam."""
    handler = _COMMANDS.get(str(args.command or ""))
    if handler is None:
        return context.argument_error(
            context.parser,
            "the following arguments are required: command",
        )
    return handler(args, context)


def _doctor(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_doctor_command(args, runtime_from_args=context.workspace_runtime_from_args)


def _install(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_install_command(args, runtime_from_args=context.workspace_runtime_from_args)


def _home(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_home_command(args, context.parser, argument_error=context.argument_error)


def _okf(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_okf_command(
        args,
        context.parser,
        runtime_from_args=context.runtime_from_args,
        argument_error=context.argument_error,
    )


def _usage(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_usage_command(args, context.parser, argument_error=context.argument_error)


def _service(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_service_command(args, context.parser, argument_error=context.argument_error)


def _automation(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_automation_command(args, context.parser, argument_error=context.argument_error)


def _publish(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_publish_command(args, context.parser, argument_error=context.argument_error)


def _watch(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_watch_command(
        args,
        context.parser,
        tags_from_args=context.tags_from_args,
        argument_error=context.argument_error,
    )


def _blog(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_blog_command(
        args,
        context.parser,
        tags_from_args=context.tags_from_args,
        argument_error=context.argument_error,
    )


def _radar(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_radar_command(args, context.parser, argument_error=context.argument_error)


def _hub(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_hub_command(args, context.parser, argument_error=context.argument_error)


def _global(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_global_command(
        args,
        context.parser,
        runtime_from_args=context.runtime_from_args,
        argument_error=context.argument_error,
    )


def _kb(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_kb_command(args, context.parser, argument_error=context.argument_error)


def _inbox(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_inbox_command(
        args,
        context.parser,
        runtime_from_args=context.workspace_runtime_from_args,
        tags_from_args=context.tags_from_args,
        takeaway_reader=context.selected_takeaways_from_args,
        print_inbox_post=context.print_inbox_post,
        print_path=context.print_path,
        argument_error=context.argument_error,
    )


def _knowledge(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_knowledge_command(
        args,
        context.parser,
        runtime_from_args=context.workspace_runtime_from_args,
        tags_from_args=context.tags_from_args,
        refs_from_args=context.refs_from_args,
        print_path=context.print_path,
        argument_error=context.argument_error,
    )


def _search(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_search_command(
        args,
        context.parser,
        runtime_from_args=context.runtime_from_args,
        print_search_rows=context.print_search_rows,
        argument_error=context.argument_error,
    )


def _pin(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_pin_command(
        args,
        context.parser,
        runtime_from_args=context.runtime_from_args,
        tags_from_args=context.tags_from_args,
        refs_from_args=context.refs_from_args,
        resources_from_args=context.resources_from_args,
        optional_tags_from_args=context.optional_tags_from_args,
        optional_refs_from_args=context.optional_refs_from_args,
        optional_resources_from_args=context.optional_resources_from_args,
        print_path=context.print_path,
        argument_error=context.argument_error,
    )


def _project(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_project_command(
        args,
        context.parser,
        runtime_from_args=context.runtime_from_args,
        argument_error=context.argument_error,
    )


def _prompt(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_prompt_command(
        args,
        context.parser,
        runtime_from_args=context.runtime_from_args,
        tags_from_args=context.tags_from_args,
        refs_from_args=context.refs_from_args,
        split_csv_values=context.split_csv_values,
        argument_error=context.argument_error,
    )


def _idea(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_idea_command(
        args,
        context.parser,
        runtime_from_args=context.runtime_from_args,
        tags_from_args=context.tags_from_args,
        optional_tags_from_args=context.optional_tags_from_args,
        routine_schedule_from_args=context.routine_schedule_from_args,
        argument_error=context.argument_error,
    )


def _task(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_task_command(
        args,
        context.parser,
        runtime_from_args=context.runtime_from_args,
        tags_from_args=context.tags_from_args,
        optional_tags_from_args=context.optional_tags_from_args,
        routine_schedule_from_args=context.routine_schedule_from_args,
        argument_error=context.argument_error,
    )


def _mount(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_mount_command(
        args,
        context.parser,
        runtime_from_args=context.runtime_from_args,
        tags_from_args=context.tags_from_args,
        argument_error=context.argument_error,
    )


def _connector(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_connector_command(
        args,
        context.parser,
        runtime_from_args=context.runtime_from_args,
        tags_from_args=context.tags_from_args,
        argument_error=context.argument_error,
    )


def _link(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_link_command(
        args,
        context.parser,
        runtime_from_args=context.workspace_runtime_from_args,
        print_path=context.print_path,
        argument_error=context.argument_error,
    )


def _export(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_export_command(
        args,
        context.parser,
        runtime_from_args=context.runtime_from_args,
        argument_error=context.argument_error,
    )


def _dashboard(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_dashboard_command(args, context.parser, argument_error=context.argument_error)


def _serve(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_serve_command(
        args,
        context.parser,
        workspace_from_args=context.workspace_from_args,
        argument_error=context.argument_error,
    )


def _validate(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_validate_command(args, runtime_from_args=context.workspace_runtime_from_args)


def _gardener(args: argparse.Namespace, context: CliDispatchContext) -> int:
    return handle_gardener_command(args, runtime_from_args=context.workspace_runtime_from_args)


_COMMANDS: dict[str, CommandHandler] = {
    "init": lambda args, _context: handle_init_command(args),
    "status": lambda args, _context: handle_status_command(args),
    "doctor": _doctor,
    "health": lambda args, context: handle_health_command(
        args,
        runtime_from_args=context.health_runtime_from_args,
    ),
    "install": _install,
    "home": _home,
    "okf": _okf,
    "usage": _usage,
    "service": _service,
    "automation": _automation,
    "publish": _publish,
    "watch": _watch,
    "blog": _blog,
    "radar": _radar,
    "hub": _hub,
    "global": _global,
    "kb": _kb,
    "inbox": _inbox,
    "knowledge": _knowledge,
    "search": _search,
    "pin": _pin,
    "project": _project,
    "prompt": _prompt,
    "idea": _idea,
    "task": _task,
    "mount": _mount,
    "connector": _connector,
    "link": _link,
    "export": _export,
    "dashboard": _dashboard,
    "serve": _serve,
    "validate": _validate,
    "gardener": _gardener,
}
