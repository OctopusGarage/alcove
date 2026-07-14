from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from alcove import __version__
from alcove.cli_publish_parser import add_publish_parser
from alcove.cli_registry import CliDispatchContext, dispatch_cli_command
from alcove.cli_workspace_parser import add_workspace_parser
from alcove.errors import AlcoveError, WorkspaceNotFoundError
from alcove.runtime import AlcoveRuntime
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

    doctor = sub.add_parser("doctor", help="Check Alcove workspace health")
    doctor.add_argument("--workspace")
    doctor.add_argument("--home")
    doctor.add_argument("--kb")
    doctor.add_argument("--json", action="store_true")

    health = sub.add_parser("health", help="Check Alcove data, OKF, and index health")
    health.add_argument("--workspace")
    health.add_argument("--home")
    health.add_argument("--kb")
    health.add_argument("--strict", action="store_true")
    health.add_argument("--fix", action="store_true")
    health.add_argument("--deep", action="store_true")
    health.add_argument("--refresh-stale-connectors", action="store_true")
    health.add_argument("--refresh-all-connectors", action="store_true")
    health.add_argument("--fixture-context", action="store_true", help=argparse.SUPPRESS)
    health.add_argument("--json", action="store_true")

    install = sub.add_parser("install", help="Install Alcove MCP config for agents")
    install.add_argument("--home")
    install.add_argument("--workspace")
    install.add_argument("--kb")
    install.add_argument("--target", action="append")
    install.add_argument("--toolset", default="full")
    install.add_argument("--print", dest="print_config", action="store_true")
    install.add_argument("--status", action="store_true")
    install.add_argument("--uninstall", action="store_true")
    install.add_argument("--json", action="store_true")

    home_cmd = sub.add_parser("home", help="Manage Alcove home")
    home_sub = home_cmd.add_subparsers(dest="home_command", required=True)
    home_init = home_sub.add_parser("init", help="Initialize Alcove home")
    home_init.add_argument("--home")
    home_init.add_argument("--json", action="store_true")

    okf = sub.add_parser("okf", help="Build derived OKF catalogs")
    okf.add_argument("--home")
    okf_sub = okf.add_subparsers(dest="okf_command", required=True)
    okf_catalog = okf_sub.add_parser("catalog", help="Build the global OKF catalog")
    okf_catalog_sub = okf_catalog.add_subparsers(dest="okf_catalog_command", required=True)
    okf_catalog_build = okf_catalog_sub.add_parser(
        "build", help="Build ~/.alcove/okf from module source-of-truth data"
    )
    okf_catalog_build.add_argument("--include-all-status", action="store_true")
    okf_catalog_build.add_argument("--json", action="store_true")

    hub = sub.add_parser("hub", help="Manage an Alcove hub workspace")
    hub_sub = hub.add_subparsers(dest="hub_command", required=True)
    hub_init = hub_sub.add_parser("init", help="Initialize a hub workspace")
    hub_init.add_argument("path")
    hub_init.add_argument("--home")
    hub_init.add_argument("--default-kb", default="")
    hub_init.add_argument("--target", action="append")
    hub_init.add_argument("--link", action="store_true")
    hub_init.add_argument("--status", action="store_true")
    hub_init.add_argument("--json", action="store_true")
    hub_install = hub_sub.add_parser("install", help="Install hub entry files")
    hub_install.add_argument("path")
    hub_install.add_argument("--home")
    hub_install.add_argument("--default-kb", default="")
    hub_install.add_argument("--target", action="append")
    hub_install.add_argument("--link", action="store_true")
    hub_install.add_argument("--status", action="store_true")
    hub_install.add_argument("--json", action="store_true")

    add_workspace_parser(sub)

    global_cmd = sub.add_parser("global", help="Install lightweight global Alcove access")
    global_sub = global_cmd.add_subparsers(dest="global_command", required=True)
    global_install = global_sub.add_parser("install", help="Install global-lite MCP")
    global_install.add_argument("--home")
    global_install.add_argument("--target", action="append")
    global_install.add_argument("--toolset", default="lite")
    global_install.add_argument("--default-kb", default="")
    global_install.add_argument("--print", dest="print_config", action="store_true")
    global_install.add_argument("--status", action="store_true")
    global_install.add_argument("--uninstall", action="store_true")
    global_install.add_argument("--json", action="store_true")

    dashboard = sub.add_parser("dashboard", help="Build and serve the local Alcove dashboard")
    dashboard.add_argument("--home")
    dashboard_sub = dashboard.add_subparsers(dest="dashboard_command", required=True)
    dashboard_build = dashboard_sub.add_parser("build", help="Build the dashboard static site")
    dashboard_build.add_argument("--output", default="")
    dashboard_build.add_argument("--skip-frontend-build", action="store_true")
    dashboard_build.add_argument("--json", action="store_true")
    dashboard_import = dashboard_sub.add_parser("import-pins", help="Import pin text files")
    dashboard_import.add_argument("--regular-file", default="")
    dashboard_import.add_argument("--todo-file", default="")
    dashboard_import.add_argument("--json", action="store_true")

    usage = sub.add_parser("usage", help="Inspect and prune local usage telemetry")
    usage.add_argument("--home")
    usage_sub = usage.add_subparsers(dest="usage_command", required=True)
    usage_summary = usage_sub.add_parser("summary", help="Show usage summary")
    usage_summary.add_argument("--home")
    usage_summary.add_argument("--json", action="store_true")
    usage_prune = usage_sub.add_parser("prune", help="Prune old usage and activity events")
    usage_prune.add_argument("--home")
    usage_prune.add_argument("--days", type=int, default=90)
    usage_prune.add_argument("--now", default="")
    usage_prune.add_argument("--json", action="store_true")

    service = sub.add_parser("service", help="Install and run Alcove local services")
    service.add_argument("--home")
    service_sub = service.add_subparsers(dest="service_command", required=True)
    service_install = service_sub.add_parser("install", help="Install launchd services")
    service_install.add_argument("--home")
    service_install.add_argument("--dashboard", action="store_true")
    service_install.add_argument("--scheduler", action="store_true")
    service_install.add_argument("--host", default="127.0.0.1")
    service_install.add_argument("--port", type=int, default=8765)
    service_install.add_argument("--interval-minutes", type=int, default=30)
    service_install.add_argument("--load", action="store_true")
    service_install.add_argument("--json", action="store_true")
    service_uninstall = service_sub.add_parser("uninstall", help="Uninstall launchd services")
    service_uninstall.add_argument("--home")
    service_uninstall.add_argument("--dashboard", action="store_true")
    service_uninstall.add_argument("--scheduler", action="store_true")
    service_uninstall.add_argument("--unload", action="store_true")
    service_uninstall.add_argument("--json", action="store_true")
    for name in ("status", "start", "stop", "restart"):
        service_cmd = service_sub.add_parser(name, help=f"{name.title()} launchd services")
        service_cmd.add_argument("--home")
        service_cmd.add_argument("--dashboard", action="store_true")
        service_cmd.add_argument("--scheduler", action="store_true")
        service_cmd.add_argument("--json", action="store_true")
    service_tick = service_sub.add_parser("tick", help="Run one deterministic maintenance tick")
    service_tick.add_argument("--home")
    service_tick.add_argument("--retention-days", type=int, default=90)
    service_tick.add_argument("--skip-connectors", action="store_true")
    service_tick.add_argument("--skip-watchers", action="store_true")
    service_tick.add_argument("--skip-blogs", action="store_true")
    service_tick.add_argument("--skip-radars", action="store_true")
    service_tick.add_argument("--skip-automations", action="store_true")
    service_tick.add_argument("--skip-publishers", action="store_true")
    service_tick.add_argument("--skip-mounts", action="store_true")
    service_tick.add_argument("--mount-refresh-days", type=int, default=2)
    service_tick.add_argument("--skip-health-fix", action="store_true")
    service_tick.add_argument("--today", default="")
    service_tick.add_argument("--json", action="store_true")

    add_publish_parser(sub)

    automation = sub.add_parser("automation", help="Manage local user automation jobs")
    automation.add_argument("--home")
    automation_sub = automation.add_subparsers(dest="automation_command", required=True)
    automation_list = automation_sub.add_parser("list", help="List automation jobs")
    automation_list.add_argument("--home", default=argparse.SUPPRESS)
    automation_list.add_argument("--status", default="active")
    automation_list.add_argument("--json", action="store_true")
    automation_run = automation_sub.add_parser("run", help="Run one automation job")
    automation_run.add_argument("--home", default=argparse.SUPPRESS)
    automation_run.add_argument("job_id")
    automation_run.add_argument("--allow-agent", action="store_true")
    automation_run.add_argument("--json", action="store_true")
    automation_due = automation_sub.add_parser("run-due", help="Run due automation jobs")
    automation_due.add_argument("--home", default=argparse.SUPPRESS)
    automation_due.add_argument("--allow-agent", action="store_true")
    automation_due.add_argument("--json", action="store_true")
    automation_shell = automation_sub.add_parser("add-shell", help="Add a shell automation job")
    automation_shell.add_argument("--home", default=argparse.SUPPRESS)
    automation_shell.add_argument("name")
    automation_shell.add_argument("--cmd", required=True)
    automation_shell.add_argument("--cwd", default="")
    automation_shell.add_argument("--ttl-hours", type=int, default=24)
    automation_shell.add_argument("--timeout-seconds", type=int, default=600)
    automation_shell.add_argument("--notify", action="store_true")
    automation_shell.add_argument("--json", action="store_true")
    automation_git = automation_sub.add_parser("add-git-sync", help="Add a git commit/push job")
    automation_git.add_argument("--home", default=argparse.SUPPRESS)
    automation_git.add_argument("name")
    automation_git.add_argument("repo_path")
    automation_git.add_argument("--commit-message", default="chore: sync local data")
    automation_git.add_argument("--ttl-hours", type=int, default=24)
    automation_git.add_argument("--timeout-seconds", type=int, default=60)
    automation_git.add_argument("--notify", action="store_true")
    automation_git.add_argument("--json", action="store_true")
    watch = sub.add_parser("watch", help="Manage watched external update sources")
    watch.add_argument("--home")
    watch_sub = watch.add_subparsers(dest="watch_command", required=True)
    watch_add = watch_sub.add_parser("add", help="Add a watched URL or feed")
    watch_add.add_argument("--home")
    watch_add.add_argument("title")
    watch_add.add_argument("url")
    watch_add.add_argument("--kind", default="page")
    watch_add.add_argument("--kb", default="")
    watch_add.add_argument("--tag", action="append", default=[])
    watch_add.add_argument("--tags", default="")
    watch_add.add_argument("--ttl-hours", type=int, default=24)
    watch_add.add_argument("--json", action="store_true")
    watch_list = watch_sub.add_parser("list", help="List watched sources")
    watch_list.add_argument("--home")
    watch_list.add_argument("--status", default="active")
    watch_list.add_argument("--json", action="store_true")
    watch_check = watch_sub.add_parser("check", help="Check watched sources")
    watch_check.add_argument("--home")
    watch_check.add_argument("source_id", nargs="?", default="")
    watch_check.add_argument("--stale", action="store_true")
    watch_check.add_argument("--json", action="store_true")

    blog = sub.add_parser("blog", help="Monitor blogs and capture new articles")
    blog.add_argument("--home")
    blog_sub = blog.add_subparsers(dest="blog_command", required=True)
    blog_add = blog_sub.add_parser("add", help="Add or update a monitored blog source")
    blog_add.add_argument("--home", default=argparse.SUPPRESS)
    blog_add.add_argument("name")
    blog_add.add_argument("url")
    blog_add.add_argument("--id", dest="source_id", default="")
    blog_add.add_argument("--discover", default="requests")
    blog_add.add_argument("--link-pattern", default="")
    blog_add.add_argument("--days-back", type=int, default=30)
    blog_add.add_argument("--capture", action="store_true")
    blog_add.add_argument("--adapter", default="clipsmith")
    blog_add.add_argument("--kb", default="")
    blog_add.add_argument("--inbox-path", default="")
    blog_add.add_argument("--summary", action="store_true")
    blog_add.add_argument("--notify", action="store_true")
    blog_add.add_argument("--tag", action="append", default=[])
    blog_add.add_argument("--tags", default="")
    blog_add.add_argument("--ttl-hours", type=int, default=24)
    blog_add.add_argument("--json", action="store_true")
    blog_list = blog_sub.add_parser("list", help="List monitored blog sources")
    blog_list.add_argument("--home", default=argparse.SUPPRESS)
    blog_list.add_argument("--status", default="active")
    blog_list.add_argument("--json", action="store_true")
    blog_seed = blog_sub.add_parser("seed", help="Initialize seen URLs without capture")
    blog_seed.add_argument("--home", default=argparse.SUPPRESS)
    blog_seed.add_argument("source_id", nargs="?", default="")
    blog_seed.add_argument("--json", action="store_true")
    blog_check = blog_sub.add_parser("check", help="Check monitored blogs for new articles")
    blog_check.add_argument("--home", default=argparse.SUPPRESS)
    blog_check.add_argument("source_id", nargs="?", default="")
    blog_check.add_argument("--stale", action="store_true")
    blog_check.add_argument("--no-capture", action="store_true")
    blog_check.add_argument("--summary", action="store_true")
    blog_check.add_argument("--notify", action="store_true")
    blog_check.add_argument("--json", action="store_true")

    radar = sub.add_parser("radar", help="Manage configurable information radars")
    radar.add_argument("--home")
    radar_sub = radar.add_subparsers(dest="radar_command", required=True)
    radar_list = radar_sub.add_parser("list", help="List configured radar definitions")
    radar_list.add_argument("--home", default=argparse.SUPPRESS)
    radar_list.add_argument("--status", default="active")
    radar_list.add_argument("--json", action="store_true")
    radar_init = radar_sub.add_parser("init", help="Create a radar definition")
    radar_init.add_argument("radar_id")
    radar_init.add_argument("--home", default=argparse.SUPPRESS)
    radar_init.add_argument("--from-preset", default="")
    radar_init.add_argument("--force", action="store_true")
    radar_init.add_argument("--json", action="store_true")
    radar_run = radar_sub.add_parser("run", help="Run a radar definition")
    radar_run.add_argument("radar_id")
    radar_run.add_argument("--home", default=argparse.SUPPRESS)
    radar_run.add_argument("--skip-fetch", action="store_true")
    radar_run.add_argument("--force", action="store_true")
    radar_run.add_argument("--ai", action="store_true")
    radar_run.add_argument("--notify", action="store_true")
    radar_run.add_argument("--json", action="store_true")
    radar_status = radar_sub.add_parser("status", help="Show radar run status")
    radar_status.add_argument("radar_id", nargs="?", default="")
    radar_status.add_argument("--home", default=argparse.SUPPRESS)
    radar_status.add_argument("--json", action="store_true")
    radar_preset = radar_sub.add_parser("preset", help="Work with packaged radar presets")
    radar_preset.add_argument("--home", default=argparse.SUPPRESS)
    radar_preset_sub = radar_preset.add_subparsers(dest="radar_preset_command", required=True)
    radar_preset_list = radar_preset_sub.add_parser("list", help="List packaged radar presets")
    radar_preset_list.add_argument("--home", default=argparse.SUPPRESS)
    radar_preset_list.add_argument("--json", action="store_true")

    kb = sub.add_parser("kb", help="Register and list managed knowledge bases")
    kb.add_argument("--home")
    kb_sub = kb.add_subparsers(dest="kb_command", required=True)
    kb_add = kb_sub.add_parser("add", help="Register a managed knowledge base")
    kb_add.add_argument("name")
    kb_add.add_argument("path")
    kb_add.add_argument("--json", action="store_true")
    kb_list = kb_sub.add_parser("list", help="List registered managed knowledge bases")
    kb_list.add_argument("--json", action="store_true")
    kb_install = kb_sub.add_parser("install", help="Install managed KB entry files")
    kb_install.add_argument("name")
    kb_install.add_argument("--target", action="append")
    kb_install.add_argument("--link", action="store_true")
    kb_install.add_argument("--status", action="store_true")
    kb_install.add_argument("--json", action="store_true")

    inbox = sub.add_parser("inbox", help="Work with inbox items")
    inbox.add_argument("--workspace")
    inbox.add_argument("--home")
    inbox.add_argument("--kb")
    inbox_sub = inbox.add_subparsers(dest="inbox_command", required=True)
    inbox_peek = inbox_sub.add_parser("peek", help="Show the oldest inbox item")
    inbox_peek.add_argument("--json", action="store_true")
    inbox_read = inbox_sub.add_parser("read", help="Read an inbox item")
    inbox_read.add_argument("name")
    inbox_read.add_argument(
        "--full",
        action="store_true",
        help="Return the unabridged merged inbox payload",
    )
    inbox_read.add_argument("--json", action="store_true")
    inbox_classify = inbox_sub.add_parser("classify", help="Suggest topic, tags, and summary")
    inbox_classify.add_argument("name")
    inbox_classify.add_argument("topic", nargs="?")
    inbox_archive = inbox_sub.add_parser("archive", help="Archive an inbox item as Source")
    inbox_archive.add_argument("name")
    inbox_archive.add_argument("topic")
    inbox_archive.add_argument("--summary", default="")
    inbox_archive.add_argument("--tag", action="append", default=[])
    inbox_archive.add_argument("--tags", default="")
    inbox_archive.add_argument("--no-auto-tags", action="store_true")
    inbox_archive.add_argument("--supersede-similar", action="store_true")
    inbox_archive.add_argument("--validate", action="store_true")
    inbox_archive.add_argument("--json", action="store_true")
    inbox_note = inbox_sub.add_parser("note", help="Archive an inbox item into knowledge")
    inbox_note.add_argument("name")
    inbox_note.add_argument("topic")
    inbox_note.add_argument("--summary", required=True)
    inbox_note.add_argument("--tag", action="append", default=[])
    inbox_note.add_argument("--tags", default="")
    inbox_note.add_argument("--selected-takeaways", default="")
    inbox_note.add_argument("--why", default="")
    inbox_note.add_argument("--connection", default="")
    inbox_note.add_argument("--action", default="")
    inbox_note.add_argument("--personal-note", default="")
    inbox_note.add_argument("--no-auto-tags", action="store_true")
    inbox_note.add_argument("--supersede-similar", action="store_true")
    inbox_note.add_argument("--validate", action="store_true")
    inbox_note.add_argument("--json", action="store_true")
    inbox_manual = inbox_sub.add_parser("manual-add", help="Add manual content to inbox")
    inbox_manual.add_argument("title")
    inbox_manual.add_argument("--content", required=True)
    inbox_manual.add_argument("--source", default="")
    inbox_manual.add_argument("--json", action="store_true")
    inbox_todo = inbox_sub.add_parser("todo", help="Move an inbox item to todo")
    inbox_todo.add_argument("name")
    inbox_todo.add_argument("reason", nargs="?", default="")
    inbox_delete = inbox_sub.add_parser("delete", help="Delete an inbox item")
    inbox_delete.add_argument("name")
    inbox_delete.add_argument("--confirm", action="store_true")

    knowledge = sub.add_parser("knowledge", help="Work with knowledge notes")
    knowledge.add_argument("--workspace")
    knowledge.add_argument("--home")
    knowledge.add_argument("--kb")
    knowledge_sub = knowledge.add_subparsers(dest="knowledge_command", required=True)
    note_source = knowledge_sub.add_parser("note-source", help="Record a source note")
    note_source.add_argument("--platform", required=True)
    note_source.add_argument("--title", required=True)
    note_source.add_argument("--topic", required=True)
    note_source.add_argument("--resource", default="")
    note_source.add_argument("--summary", required=True)
    note_source.add_argument("--tag", action="append", default=[])
    add_note = knowledge_sub.add_parser("add-note", help="Add a standalone concept")
    add_note.add_argument("topic")
    add_note.add_argument("title")
    add_note.add_argument("--summary", default="")
    add_note.add_argument("--tag", action="append", default=[])
    add_note.add_argument("--tags", default="")
    revise = knowledge_sub.add_parser("revise", help="Revise an existing OKF knowledge note")
    revise.add_argument("path")
    revise.add_argument("--summary", default="")
    revise.add_argument("--answer", default="")
    revise.add_argument("--append", default="")
    revise.add_argument("--tag", action="append", default=[])
    revise.add_argument("--tags", default="")
    revise.add_argument("--source-ref", action="append", default=[])
    revise.add_argument("--source-refs", default="")
    revise.add_argument("--reason", default="")
    revise.add_argument("--status", default="")
    revise.add_argument("--json", action="store_true")
    knowledge_delete = knowledge_sub.add_parser(
        "delete",
        help="Soft-delete a knowledge result by path after confirmation",
    )
    knowledge_delete.add_argument("path")
    knowledge_delete.add_argument("--reason", default="")
    knowledge_delete.add_argument("--confirm", action="store_true")
    knowledge_delete.add_argument("--json", action="store_true")
    add_question = knowledge_sub.add_parser("add-question", help="Add a reusable question")
    add_question.add_argument("topic")
    add_question.add_argument("question")
    add_question.add_argument("--answer", default="")
    add_question.add_argument("--tag", action="append", default=[])
    add_question.add_argument("--tags", default="")
    add_question.add_argument("--source-ref", action="append", default=[])
    add_question.add_argument("--source-refs", default="")
    add_entity = knowledge_sub.add_parser("add-entity", help="Add a reusable entity")
    add_entity.add_argument("topic")
    add_entity.add_argument("name")
    add_entity.add_argument("--kind", default="object")
    add_entity.add_argument("--summary", default="")
    add_entity.add_argument("--use-cases", default="")
    add_entity.add_argument("--open-questions", default="")
    add_entity.add_argument("--tag", action="append", default=[])
    add_entity.add_argument("--tags", default="")
    add_entity.add_argument("--source-ref", action="append", default=[])
    add_entity.add_argument("--source-refs", default="")
    promote = knowledge_sub.add_parser("promote", help="Promote a Source to a Concept")
    promote.add_argument("source")
    promote.add_argument("--topic", default="")
    promote.add_argument("--summary", default="")
    refresh = knowledge_sub.add_parser(
        "refresh", help="Refresh a topic concept from active sources"
    )
    refresh.add_argument("topic")
    refresh.add_argument("--in-place", action="store_true")
    refresh.add_argument("--summary", default="")
    knowledge_sub.add_parser("topics", help="List known topics/tags/domains")

    validate = sub.add_parser("validate", help="Validate an Alcove workspace")
    validate.add_argument("--workspace")
    validate.add_argument("--home")
    validate.add_argument("--kb")
    validate.add_argument("--strict-quality", action="store_true")
    validate.add_argument("--json", action="store_true")

    gardener = sub.add_parser("gardener", help="Scan knowledge health")
    gardener.add_argument("--workspace")
    gardener.add_argument("--home")
    gardener.add_argument("--kb")
    gardener.add_argument("--prune", action="store_true")
    gardener.add_argument("--json", action="store_true")

    pin = sub.add_parser("pin", help="Work with pinned personal notes")
    pin.add_argument("--workspace")
    pin.add_argument("--home")
    pin_sub = pin.add_subparsers(dest="pin_command", required=True)
    pin_add = pin_sub.add_parser("add", help="Add a pinned personal note")
    pin_add.add_argument("title")
    pin_add.add_argument("--description", default="")
    pin_add.add_argument("--summary", default="")
    pin_add.add_argument("--content", default="")
    pin_add.add_argument("--kind", default="regular")
    pin_add.add_argument("--tag", action="append", default=[])
    pin_add.add_argument("--tags", default="")
    pin_add.add_argument("--priority", default="medium")
    pin_add.add_argument("--source-ref", action="append", default=[])
    pin_add.add_argument("--source-refs", default="")
    pin_add.add_argument("--resource", action="append", default=[])
    pin_add.add_argument("--resources", default="")
    pin_add.add_argument("--content-format", default="text")
    pin_add.add_argument("--json", action="store_true")
    pin_get = pin_sub.add_parser("get", help="Get a pinned personal note")
    pin_get.add_argument("pin_id")
    pin_get.add_argument("--json", action="store_true")
    pin_list = pin_sub.add_parser("list", help="List pinned personal notes")
    pin_list.add_argument("--tag")
    pin_list.add_argument("--status", default="active")
    pin_list.add_argument("--json", action="store_true")
    pin_search = pin_sub.add_parser("search", help="Search pinned personal notes")
    pin_search.add_argument("query", nargs="?", default="")
    pin_search.add_argument("--kind", default="")
    pin_search.add_argument("--tag", default="")
    pin_search.add_argument("--status", default="active")
    pin_search.add_argument("--json", action="store_true")
    pin_update = pin_sub.add_parser("update", help="Update a pinned personal note")
    pin_update.add_argument("pin_id")
    pin_update.add_argument("--title")
    pin_update.add_argument("--description")
    pin_update.add_argument("--summary")
    pin_update.add_argument("--content")
    pin_update.add_argument("--kind")
    pin_update.add_argument("--tag", action="append")
    pin_update.add_argument("--tags")
    pin_update.add_argument("--priority")
    pin_update.add_argument("--source-ref", action="append")
    pin_update.add_argument("--source-refs")
    pin_update.add_argument("--resource", action="append")
    pin_update.add_argument("--resources")
    pin_update.add_argument("--status")
    pin_update.add_argument("--content-format")
    pin_update.add_argument("--json", action="store_true")
    pin_index = pin_sub.add_parser("rebuild-index", help="Rebuild the pins index")
    pin_index.add_argument("--json", action="store_true")
    pin_html = pin_sub.add_parser("render-html", help="Render the pins HTML board")
    pin_html.add_argument("--output", default="")
    pin_html.add_argument("--json", action="store_true")
    pin_archive = pin_sub.add_parser("archive", help="Archive a pin")
    pin_archive.add_argument("pin_id")
    pin_archive.add_argument("--confirm", action="store_true")
    pin_archive.add_argument("--json", action="store_true")

    project = sub.add_parser("project", help="Work with global project aliases")
    project.add_argument("--workspace")
    project.add_argument("--home")
    project_sub = project.add_subparsers(dest="project_command", required=True)
    project_add = project_sub.add_parser("add", help="Add a project alias")
    project_add.add_argument("alias")
    project_add.add_argument("path")
    project_add.add_argument("--note", default="")
    project_add.add_argument("--json", action="store_true")
    project_get = project_sub.add_parser("get", help="Get a project alias")
    project_get.add_argument("alias")
    project_get.add_argument("--json", action="store_true")
    project_find = project_sub.add_parser("find", help="Find project aliases or scanned roots")
    project_find.add_argument("keyword")
    project_find.add_argument("--json", action="store_true")
    project_list = project_sub.add_parser("list", help="List project aliases")
    project_list.add_argument("--json", action="store_true")
    project_remove = project_sub.add_parser("remove", help="Remove a project alias")
    project_remove.add_argument("alias")
    project_remove.add_argument("--json", action="store_true")
    project_roots = project_sub.add_parser("roots-set", help="Set project root scan paths")
    project_roots.add_argument("roots", nargs="+")
    project_roots.add_argument("--json", action="store_true")

    prompt = sub.add_parser("prompt", help="Work with reusable global prompts")
    prompt.add_argument("--workspace")
    prompt.add_argument("--home")
    prompt_sub = prompt.add_subparsers(dest="prompt_command", required=True)
    prompt_save = prompt_sub.add_parser("save", help="Save or update a global prompt")
    prompt_save.add_argument("title", nargs="?")
    prompt_save.add_argument("--content", default="")
    prompt_save.add_argument("--proposal-id", default="")
    prompt_save.add_argument("--force", action="store_true")
    prompt_save.add_argument("--description", default="")
    prompt_save.add_argument("--tag", action="append", default=[])
    prompt_save.add_argument("--tags", action="append", default=[])
    prompt_save.add_argument("--use-case", action="append", default=[])
    prompt_save.add_argument("--use-cases", action="append", default=[])
    prompt_save.add_argument("--source-ref", action="append", default=[])
    prompt_save.add_argument("--source-refs", action="append", default=[])
    prompt_save.add_argument("--kind", default="full_prompt")
    prompt_save.add_argument("--domain", default="")
    prompt_save.add_argument("--intent", default="")
    prompt_save.add_argument("--surface", action="append", default=[])
    prompt_save.add_argument("--surfaces", action="append", default=[])
    prompt_save.add_argument("--trigger", action="append", default=[])
    prompt_save.add_argument("--triggers", action="append", default=[])
    prompt_save.add_argument("--input", action="append", default=[])
    prompt_save.add_argument("--inputs", action="append", default=[])
    prompt_save.add_argument("--output", action="append", default=[])
    prompt_save.add_argument("--outputs", action="append", default=[])
    prompt_save.add_argument("--quality-status", default="")
    prompt_save.add_argument("--quality-score", type=float)
    prompt_save.add_argument("--quality-notes", default="")
    prompt_save.add_argument("--json", action="store_true")
    prompt_propose = prompt_sub.add_parser(
        "propose", help="Prepare and deduplicate a prompt before saving"
    )
    prompt_propose.add_argument("title", nargs="?")
    prompt_propose.add_argument("--content", required=True)
    prompt_propose.add_argument("--description", default="")
    prompt_propose.add_argument("--tag", action="append", default=[])
    prompt_propose.add_argument("--tags", action="append", default=[])
    prompt_propose.add_argument("--use-case", action="append", default=[])
    prompt_propose.add_argument("--use-cases", action="append", default=[])
    prompt_propose.add_argument("--source-ref", action="append", default=[])
    prompt_propose.add_argument("--source-refs", action="append", default=[])
    prompt_propose.add_argument("--kind", default="full_prompt")
    prompt_propose.add_argument("--domain", default="")
    prompt_propose.add_argument("--intent", default="")
    prompt_propose.add_argument("--surface", action="append", default=[])
    prompt_propose.add_argument("--surfaces", action="append", default=[])
    prompt_propose.add_argument("--trigger", action="append", default=[])
    prompt_propose.add_argument("--triggers", action="append", default=[])
    prompt_propose.add_argument("--input", action="append", default=[])
    prompt_propose.add_argument("--inputs", action="append", default=[])
    prompt_propose.add_argument("--output", action="append", default=[])
    prompt_propose.add_argument("--outputs", action="append", default=[])
    prompt_propose.add_argument("--quality-status", default="")
    prompt_propose.add_argument("--quality-score", type=float)
    prompt_propose.add_argument("--quality-notes", default="")
    prompt_propose.add_argument(
        "--ai-eval-provider",
        choices=["none", "codex", "claude"],
        default="",
        help="Optionally run a real Codex/Claude prompt-quality reviewer for this proposal",
    )
    prompt_propose.add_argument("--json", action="store_true")
    prompt_proposal = prompt_sub.add_parser("proposal", help="Show a saved prompt proposal")
    prompt_proposal.add_argument("proposal_id")
    prompt_proposal.add_argument("--json", action="store_true")
    prompt_search = prompt_sub.add_parser("search", help="Search reusable global prompts")
    prompt_search.add_argument("query", nargs="?", default="")
    prompt_search.add_argument("--tag", default="")
    prompt_search.add_argument("--status", default="active")
    prompt_search.add_argument("--kind", default="")
    prompt_search.add_argument("--domain", default="")
    prompt_search.add_argument("--surface", default="")
    prompt_search.add_argument("--json", action="store_true")
    prompt_recommend = prompt_sub.add_parser(
        "recommend", help="Recommend reusable prompts for a scenario"
    )
    prompt_recommend.add_argument("scenario")
    prompt_recommend.add_argument("--limit", type=int, default=5)
    prompt_recommend.add_argument("--status", default="active")
    prompt_recommend.add_argument("--surface", default="")
    prompt_recommend.add_argument("--json", action="store_true")
    prompt_compose = prompt_sub.add_parser(
        "compose", help="Compose a ready-to-use prompt pack for a scenario"
    )
    prompt_compose.add_argument("scenario")
    prompt_compose.add_argument("--limit", type=int, default=4)
    prompt_compose.add_argument("--status", default="active")
    prompt_compose.add_argument("--surface", default="")
    prompt_compose.add_argument("--max-chars-per-prompt", type=int, default=1800)
    prompt_compose.add_argument("--json", action="store_true")
    prompt_audit = prompt_sub.add_parser("audit", help="Audit prompt library quality")
    prompt_audit.add_argument("--status", default="active")
    prompt_audit.add_argument("--json", action="store_true")
    prompt_candidates = prompt_sub.add_parser(
        "candidates", help="Manage imported prompt candidates"
    )
    prompt_candidates_sub = prompt_candidates.add_subparsers(
        dest="prompt_candidates_command", required=True
    )
    prompt_candidates_scan = prompt_candidates_sub.add_parser(
        "scan", help="Scan source files or folders into prompt candidates"
    )
    prompt_candidates_scan.add_argument("paths", nargs="+")
    prompt_candidates_scan.add_argument("--json", action="store_true")
    prompt_candidates_list = prompt_candidates_sub.add_parser(
        "list", help="List scanned prompt candidates"
    )
    prompt_candidates_list.add_argument("--min-score", type=float, default=0.0)
    prompt_candidates_list.add_argument("--json", action="store_true")
    prompt_candidates_promote = prompt_candidates_sub.add_parser(
        "promote", help="Promote high-quality candidates into the prompt library"
    )
    prompt_candidates_promote.add_argument("--min-score", type=float, default=0.72)
    prompt_candidates_promote.add_argument("--limit", type=int, default=0)
    prompt_candidates_promote.add_argument("--json", action="store_true")
    prompt_get = prompt_sub.add_parser("get", help="Get a reusable global prompt")
    prompt_get.add_argument("prompt_id")
    prompt_get.add_argument("--json", action="store_true")
    prompt_archive = prompt_sub.add_parser("archive", help="Archive a reusable global prompt")
    prompt_archive.add_argument("prompt_id")
    prompt_archive.add_argument("--confirm", action="store_true")
    prompt_archive.add_argument("--json", action="store_true")
    prompt_tags = prompt_sub.add_parser("tags", help="List prompt tags")
    prompt_tags.add_argument("--json", action="store_true")
    prompt_index = prompt_sub.add_parser("rebuild-index", help="Rebuild the prompt index")
    prompt_index.add_argument("--json", action="store_true")

    idea = sub.add_parser("idea", help="Work with low-friction ideas")
    idea.add_argument("--workspace")
    idea.add_argument("--home")
    idea_sub = idea.add_subparsers(dest="idea_command", required=True)
    idea_add = idea_sub.add_parser("add", help="Add an idea")
    idea_add.add_argument("title")
    idea_add.add_argument("--notes", default="")
    idea_add.add_argument("--tag", action="append", default=[])
    idea_add.add_argument("--tags", default="")
    idea_add.add_argument("--json", action="store_true")
    idea_list = idea_sub.add_parser("list", help="List ideas")
    idea_list.add_argument("--status", default="active")
    idea_list.add_argument("--json", action="store_true")
    idea_promote = idea_sub.add_parser("promote", help="Promote an idea to a task")
    idea_promote.add_argument("idea_id")
    idea_promote.add_argument("--notes", default="")
    idea_promote.add_argument("--priority", default="medium")
    idea_promote.add_argument("--due", default="")
    idea_promote.add_argument("--json", action="store_true")
    idea_edit = idea_sub.add_parser("edit", help="Edit an idea")
    idea_edit.add_argument("idea_id")
    idea_edit.add_argument("--title")
    idea_edit.add_argument("--notes")
    idea_edit.add_argument("--tag", action="append", default=[])
    idea_edit.add_argument("--tags", default="")
    idea_edit.add_argument("--json", action="store_true")
    idea_archive = idea_sub.add_parser("archive", help="Archive an idea")
    idea_archive.add_argument("idea_id")
    idea_archive.add_argument("--json", action="store_true")
    idea_promote_routine = idea_sub.add_parser(
        "promote-routine",
        help="Promote an idea to a recurring task template",
    )
    idea_promote_routine.add_argument("idea_id")
    idea_promote_routine.add_argument("--notes", default="")
    idea_promote_routine.add_argument("--priority", default="medium")
    idea_promote_routine.add_argument("--next-due", required=True)
    idea_promote_routine.add_argument("--frequency", default="daily")
    idea_promote_routine.add_argument("--interval", type=int, default=1)
    idea_promote_routine.add_argument("--weekday", action="append", default=[])
    idea_promote_routine.add_argument("--day-of-month", type=int, default=0)
    idea_promote_routine.add_argument("--json", action="store_true")

    task = sub.add_parser("task", help="Work with personal tasks")
    task.add_argument("--workspace")
    task.add_argument("--home")
    task_sub = task.add_subparsers(dest="task_command", required=True)
    task_add = task_sub.add_parser("add", help="Add a task")
    task_add.add_argument("title")
    task_add.add_argument("--notes", default="")
    task_add.add_argument("--tag", action="append", default=[])
    task_add.add_argument("--tags", default="")
    task_add.add_argument("--priority", default="medium")
    task_add.add_argument("--due", default="")
    task_add.add_argument("--json", action="store_true")
    task_list = task_sub.add_parser("list", help="List tasks")
    task_list.add_argument("--status", default="pending")
    task_list.add_argument("--json", action="store_true")
    task_edit = task_sub.add_parser("edit", help="Edit a task")
    task_edit.add_argument("task_id")
    task_edit.add_argument("--title")
    task_edit.add_argument("--notes")
    task_edit.add_argument("--tag", action="append", default=[])
    task_edit.add_argument("--tags", default="")
    task_edit.add_argument("--priority")
    task_edit.add_argument("--due")
    task_edit.add_argument("--json", action="store_true")
    task_complete = task_sub.add_parser("complete", help="Complete a task")
    task_complete.add_argument("task_id")
    task_complete.add_argument("--json", action="store_true")
    task_cancel = task_sub.add_parser("cancel", help="Cancel a task")
    task_cancel.add_argument("task_id")
    task_cancel.add_argument("--json", action="store_true")
    routine_add = task_sub.add_parser("routine-add", help="Add a recurring task template")
    routine_add.add_argument("title")
    routine_add.add_argument("--notes", default="")
    routine_add.add_argument("--tag", action="append", default=[])
    routine_add.add_argument("--tags", default="")
    routine_add.add_argument("--priority", default="medium")
    routine_add.add_argument("--every-days", type=int, default=1)
    routine_add.add_argument("--frequency", default="")
    routine_add.add_argument("--interval", type=int, default=1)
    routine_add.add_argument("--weekday", action="append", default=[])
    routine_add.add_argument("--day-of-month", type=int, default=0)
    routine_add.add_argument("--next-due", required=True)
    routine_add.add_argument("--json", action="store_true")
    routine_list = task_sub.add_parser("routine-list", help="List recurring task templates")
    routine_list.add_argument("--status", default="active")
    routine_list.add_argument("--json", action="store_true")
    routine_edit = task_sub.add_parser("routine-edit", help="Edit a recurring task template")
    routine_edit.add_argument("routine_id")
    routine_edit.add_argument("--title")
    routine_edit.add_argument("--notes")
    routine_edit.add_argument("--tag", action="append", default=[])
    routine_edit.add_argument("--tags", default="")
    routine_edit.add_argument("--priority")
    routine_edit.add_argument("--next-due")
    routine_edit.add_argument("--frequency", default="")
    routine_edit.add_argument("--interval", type=int, default=1)
    routine_edit.add_argument("--weekday", action="append", default=[])
    routine_edit.add_argument("--day-of-month", type=int, default=0)
    routine_edit.add_argument("--json", action="store_true")
    routine_pause = task_sub.add_parser("routine-pause", help="Pause a recurring task template")
    routine_pause.add_argument("routine_id")
    routine_pause.add_argument("--json", action="store_true")
    routine_resume = task_sub.add_parser("routine-resume", help="Resume a recurring task template")
    routine_resume.add_argument("routine_id")
    routine_resume.add_argument("--today", default="")
    routine_resume.add_argument("--json", action="store_true")
    routine_archive = task_sub.add_parser(
        "routine-archive", help="Archive a recurring task template"
    )
    routine_archive.add_argument("routine_id")
    routine_archive.add_argument("--json", action="store_true")
    materialize_due = task_sub.add_parser("materialize-due", help="Create tasks for due routines")
    materialize_due.add_argument("--today", default="")
    materialize_due.add_argument("--json", action="store_true")
    task_digest = task_sub.add_parser("digest", help="Build a task/idea/routine digest")
    task_digest.add_argument("--period", default="weekly")
    task_digest.add_argument("--today", default="")
    task_digest.add_argument("--notify", action="store_true")
    task_digest.add_argument("--json", action="store_true")
    mount = sub.add_parser("mount", help="Work with mounted external sources")
    mount.add_argument("--workspace")
    mount.add_argument("--home")
    mount_sub = mount.add_subparsers(dest="mount_command", required=True)
    mount_add = mount_sub.add_parser("add", help="Add a local mount")
    mount_add.add_argument("path")
    mount_add.add_argument("--name", default="")
    mount_add.add_argument("--type", default="local-folder")
    mount_add.add_argument("--tag", action="append", default=[])
    mount_add.add_argument("--tags", default="")
    mount_add.add_argument("--profile", default="raw")
    mount_add.add_argument("--include", action="append", default=[])
    mount_add.add_argument("--exclude", action="append", default=[])
    mount_add.add_argument("--max-file-size-kb", type=int, default=976)
    mount_add.add_argument("--json", action="store_true")
    mount_update = mount_sub.add_parser("update", help="Update mount index policy")
    mount_update.add_argument("mount_id")
    mount_update.add_argument("--profile", default="")
    mount_update.add_argument("--include", action="append", default=[])
    mount_update.add_argument("--exclude", action="append", default=[])
    mount_update.add_argument("--max-file-size-kb", type=int, default=0)
    mount_update.add_argument("--json", action="store_true")
    mount_list = mount_sub.add_parser("list", help="List mounts")
    mount_list.add_argument("--status", default="active")
    mount_list.add_argument("--json", action="store_true")
    mount_scan = mount_sub.add_parser("scan", help="Scan mounted sources")
    mount_scan.add_argument("mount_id", nargs="?")
    mount_scan.add_argument("--include-diagnostics", action="store_true")
    mount_scan.add_argument("--dry-run", action="store_true")
    mount_scan.add_argument("--json", action="store_true")

    connector = sub.add_parser("connector", help="Work with external connectors")
    connector.add_argument("--workspace")
    connector.add_argument("--home")
    connector_sub = connector.add_subparsers(dest="connector_command", required=True)
    connector_status = connector_sub.add_parser("status", help="Show registered connector sources")
    connector_status.add_argument("--connector", default="")
    connector_status.add_argument("--json", action="store_true")
    connector_refresh = connector_sub.add_parser(
        "refresh", help="Refresh registered connector sources"
    )
    connector_refresh.add_argument("--connector", default="")
    connector_refresh.add_argument("--stale", action="store_true")
    connector_refresh.add_argument("--all", action="store_true")
    connector_refresh.add_argument("--include-diff", action="store_true")
    connector_refresh.add_argument("--json", action="store_true")
    connector_fetch = connector_sub.add_parser("fetch", help="Fetch indexed connector item detail")
    connector_fetch.add_argument("item_path")
    connector_fetch.add_argument("--json", action="store_true")
    apple_notes = connector_sub.add_parser("apple-notes", help="Index Apple Notes exports")
    apple_notes_sub = apple_notes.add_subparsers(dest="apple_notes_command", required=True)
    apple_notes_index = apple_notes_sub.add_parser(
        "index", help="Index a deterministic Apple Notes export directory"
    )
    apple_notes_index.add_argument("export_dir")
    apple_notes_index.add_argument("--tag", action="append", default=[])
    apple_notes_index.add_argument("--tags", default="")
    apple_notes_index.add_argument("--include-items", action="store_true")
    apple_notes_index.add_argument("--json", action="store_true")
    apple_notes_import_local = apple_notes_sub.add_parser(
        "import-local",
        help="Export local Notes.app notes into Alcove, then index them",
    )
    apple_notes_import_local.add_argument("--export-dir", default="")
    apple_notes_import_local.add_argument("--source-id", default="local")
    apple_notes_import_local.add_argument("--tag", action="append", default=[])
    apple_notes_import_local.add_argument("--tags", default="")
    apple_notes_import_local.add_argument("--include-items", action="store_true")
    apple_notes_import_local.add_argument("--include-diff", action="store_true")
    apple_notes_import_local.add_argument("--json", action="store_true")
    apple_notes_refresh = apple_notes_sub.add_parser(
        "refresh",
        help="Refresh a registered Apple Notes source",
    )
    apple_notes_refresh.add_argument("source_id", nargs="?", default="")
    apple_notes_refresh.add_argument("--force", action="store_true")
    apple_notes_refresh.add_argument("--include-diff", action="store_true")
    apple_notes_refresh.add_argument("--json", action="store_true")
    github_stars = connector_sub.add_parser(
        "github-stars",
        help="Index a local GitHub starred repositories export",
    )
    github_stars_sub = github_stars.add_subparsers(
        dest="github_stars_command",
        required=True,
    )
    github_stars_index = github_stars_sub.add_parser(
        "index",
        help="Index a JSON export of GitHub starred repositories",
    )
    github_stars_index.add_argument("export_file")
    github_stars_index.add_argument("--tag", action="append", default=[])
    github_stars_index.add_argument("--tags", default="")
    github_stars_index.add_argument("--include-items", action="store_true")
    github_stars_index.add_argument("--json", action="store_true")
    github_stars_import_url = github_stars_sub.add_parser(
        "import-url",
        help="Fetch starred repositories from a GitHub stars page or username, then index them",
    )
    github_stars_import_url.add_argument("source")
    github_stars_import_url.add_argument("--export-file", default="")
    github_stars_import_url.add_argument("--limit", type=int, default=0)
    github_stars_import_url.add_argument("--max-pages", type=int, default=0)
    github_stars_import_url.add_argument("--tag", action="append", default=[])
    github_stars_import_url.add_argument("--tags", default="")
    github_stars_import_url.add_argument("--include-items", action="store_true")
    github_stars_import_url.add_argument("--include-diff", action="store_true")
    github_stars_import_url.add_argument("--json", action="store_true")
    github_stars_refresh = github_stars_sub.add_parser(
        "refresh",
        help="Refresh a registered GitHub Stars source",
    )
    github_stars_refresh.add_argument("source_id", nargs="?", default="")
    github_stars_refresh.add_argument("--force", action="store_true")
    github_stars_refresh.add_argument("--include-diff", action="store_true")
    github_stars_refresh.add_argument("--json", action="store_true")
    chrome_bookmarks = connector_sub.add_parser(
        "chrome-bookmarks",
        help="Index Chrome bookmarks from a local Bookmarks file or exported HTML",
    )
    chrome_bookmarks_sub = chrome_bookmarks.add_subparsers(
        dest="chrome_bookmarks_command",
        required=True,
    )
    chrome_bookmarks_index = chrome_bookmarks_sub.add_parser(
        "index",
        help="Index a Chrome Bookmarks JSON file or Netscape bookmarks HTML export",
    )
    chrome_bookmarks_index.add_argument("export_file")
    chrome_bookmarks_index.add_argument("--tag", action="append", default=[])
    chrome_bookmarks_index.add_argument("--tags", default="")
    chrome_bookmarks_index.add_argument("--include-items", action="store_true")
    chrome_bookmarks_index.add_argument("--json", action="store_true")
    chrome_bookmarks_import_local = chrome_bookmarks_sub.add_parser(
        "import-local",
        help="Index the local Chrome profile Bookmarks file and register it for refresh",
    )
    chrome_bookmarks_import_local.add_argument("--source-file", default="")
    chrome_bookmarks_import_local.add_argument("--profile", default="Default")
    chrome_bookmarks_import_local.add_argument("--source-id", default="default")
    chrome_bookmarks_import_local.add_argument("--tag", action="append", default=[])
    chrome_bookmarks_import_local.add_argument("--tags", default="")
    chrome_bookmarks_import_local.add_argument("--include-items", action="store_true")
    chrome_bookmarks_import_local.add_argument("--include-diff", action="store_true")
    chrome_bookmarks_import_local.add_argument("--json", action="store_true")
    chrome_bookmarks_refresh = chrome_bookmarks_sub.add_parser(
        "refresh",
        help="Refresh a registered Chrome Bookmarks source",
    )
    chrome_bookmarks_refresh.add_argument("source_id", nargs="?", default="")
    chrome_bookmarks_refresh.add_argument("--force", action="store_true")
    chrome_bookmarks_refresh.add_argument("--include-diff", action="store_true")
    chrome_bookmarks_refresh.add_argument("--json", action="store_true")

    link = sub.add_parser("link", help="Promote indexed external items into knowledge")
    link.add_argument("--workspace")
    link.add_argument("--home")
    link.add_argument("--kb")
    link_sub = link.add_subparsers(dest="link_command", required=True)
    link_source = link_sub.add_parser("source", help="Create a Source from an indexed item")
    link_source.add_argument("item_path")
    link_source.add_argument("topic")
    link_source.add_argument("--summary", default="")
    link_source.add_argument("--create-concept", action="store_true")
    link_source.add_argument("--json", action="store_true")

    serve = sub.add_parser("serve", help="Run Alcove local services")
    serve.add_argument("--mcp", action="store_true", help="Run the MCP server over stdio")
    serve.add_argument("--dashboard", action="store_true", help="Run the local dashboard server")
    serve.add_argument("--workspace", default="")
    serve.add_argument("--home", default="")
    serve.add_argument("--kb", default="")
    serve.add_argument("--toolset", default="full")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)

    search = sub.add_parser("search", help="Search and browse knowledge")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--workspace")
    search.add_argument("--home")
    search.add_argument("--kb")
    search.add_argument("--type", dest="type_filter")
    search.add_argument("--tag")
    search.add_argument("--topic")
    search.add_argument("--platform")
    search.add_argument("--date-from")
    search.add_argument("--date-to")
    search.add_argument("--min-confidence", type=float)
    search.add_argument("--status")
    search.add_argument("--limit", type=int, default=20)
    search.add_argument("--tags", action="store_true", help="List tags with counts")
    search.add_argument("--tag-doctor", action="store_true", help="Find tag variants")
    search.add_argument("--recent", type=int, help="List recent docs")
    search.add_argument("--unindexed", action="store_true", help="Run validation")
    search.add_argument("--json", action="store_true")

    export = sub.add_parser("export", help="Export Alcove user data")
    export.add_argument("--home")
    export_sub = export.add_subparsers(dest="export_command", required=True)
    export_global = export_sub.add_parser("global", help="Export global Alcove Home state")
    export_global.add_argument("output_dir")
    export_global.add_argument("--json", action="store_true")
    export_kb = export_sub.add_parser("kb", help="Export a managed knowledge base")
    export_kb.add_argument("name")
    export_kb.add_argument("output_dir")
    export_kb.add_argument("--json", action="store_true")
    export_all = export_sub.add_parser("all", help="Export global state and registered KBs")
    export_all.add_argument("output_dir")
    export_all.add_argument("--json", action="store_true")
    return parser


def _print_inbox_post(post) -> None:
    if isinstance(post, dict):
        date = post.get("date") or ""
        print(f"{post['platform']} | {date} | {post['title']}")
        print(f"path: {post['path']}")
        print(f"source: {post.get('source') or ''}")
        print(f"content_source: {post['content_source']}")
        content = post["content"]
    else:
        date = post.date or ""
        print(f"{post.platform} | {date} | {post.title}")
        print(f"path: {post.path}")
        print(f"source: {post.source or ''}")
        print(f"content_source: {post.content_source}")
        content = post.content
    print()
    print(content)


def _print_path(label: str, path: Path | None) -> None:
    if path is not None:
        print(f"{label}: {path}")


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _split_csv_values(values: str | list[str]) -> list[str]:
    if isinstance(values, str):
        return _split_csv(values)
    items: list[str] = []
    for value in values:
        items.extend(_split_csv(value))
    return items


def _tags(args) -> list[str]:
    return [*getattr(args, "tag", []), *_split_csv_values(getattr(args, "tags", []))]


def _routine_schedule_from_args(args, *, include_default: bool = False) -> dict[str, Any]:
    frequency = getattr(args, "frequency", "") or ("daily" if include_default else "")
    if not frequency:
        return {}
    schedule: dict[str, Any] = {
        "frequency": frequency,
        "interval": getattr(args, "interval", 1),
    }
    if frequency == "weekly":
        schedule["weekdays"] = getattr(args, "weekday", []) or []
    if frequency == "monthly":
        schedule["day_of_month"] = getattr(args, "day_of_month", 0)
    return schedule


def _refs(args) -> list[str]:
    return [
        *getattr(args, "source_ref", []),
        *_split_csv_values(getattr(args, "source_refs", [])),
    ]


def _resources(args) -> list[str]:
    return [
        *getattr(args, "resource", []),
        *_split_csv(getattr(args, "resources", "")),
    ]


def _optional_tags(args) -> list[str] | None:
    if getattr(args, "tag", None) is None and getattr(args, "tags", None) is None:
        return None
    return [*(getattr(args, "tag", None) or []), *_split_csv(getattr(args, "tags", "") or "")]


def _optional_refs(args) -> list[str] | None:
    if getattr(args, "source_ref", None) is None and getattr(args, "source_refs", None) is None:
        return None
    return [
        *(getattr(args, "source_ref", None) or []),
        *_split_csv(getattr(args, "source_refs", "") or ""),
    ]


def _optional_resources(args) -> list[str] | None:
    if getattr(args, "resource", None) is None and getattr(args, "resources", None) is None:
        return None
    return [
        *(getattr(args, "resource", None) or []),
        *_split_csv(getattr(args, "resources", "") or ""),
    ]


def _selected_takeaways(value: str) -> list[str]:
    return [
        item.strip()
        for item in value.replace("，", ",").replace("、", ",").split(",")
        if item.strip()
    ]


def _print_search_rows(rows: list[dict]) -> None:
    for row in rows:
        collected = row.get("collected_at") or ""
        updated = row.get("updated_at") or ""
        lifecycle = f"collected={collected[:10] or '-'} updated={updated[:10] or '-'}"
        print(
            f"{row.get('date') or '':<10} | "
            f"{row.get('confidence', 0.5):.2f} | "
            f"{row.get('status') or 'active':<10} | "
            f"{row.get('type')} | {row.get('topic')} | "
            f"{row.get('title')} | {lifecycle} | {row.get('path')}"
        )


def _argument_error(parser: argparse.ArgumentParser, message: str) -> int:
    parser.print_usage(sys.stderr)
    print(f"{parser.prog}: error: {message}", file=sys.stderr)
    return 2


def _json_error_payload(args: argparse.Namespace, exc: Exception) -> dict:
    command = str(getattr(args, "command", "") or "")
    connector = str(getattr(args, "connector_command", "") or "")
    error_type = exc.__class__.__name__
    message = str(exc)
    payload = {
        "error": {
            "error_code": error_type.replace("Error", "").replace("Exception", "").lower()
            or "error",
            "message": message,
            "remediation_hint": _error_remediation_hint(args, exc),
        }
    }
    operation = str(getattr(exc, "operation", "") or "")
    if operation:
        payload["error"]["operation"] = operation
    remediation_command = str(getattr(exc, "remediation_command", "") or "")
    if remediation_command:
        payload["error"]["remediation_command"] = remediation_command
    if command:
        payload["error"]["command"] = command
    if connector:
        payload["error"]["connector"] = connector
    return payload


def _error_remediation_hint(args: argparse.Namespace, exc: Exception) -> str:
    connector = str(getattr(args, "connector_command", "") or "")
    message = str(exc)
    if connector == "github-stars":
        if "Unsupported GitHub Stars URL host" in message:
            return "Use a GitHub profile URL such as https://github.com/<user>?tab=stars or pass a GitHub username."
        return "Check the GitHub Stars source, network access, and any local export file before retrying."
    if connector == "chrome-bookmarks":
        return "Export Chrome bookmarks as valid JSON or pass a readable Chrome Bookmarks file."
    if connector == "apple-notes":
        return (
            "Check that Notes.app is available and unlocked, and grant Automation access "
            "for this terminal or agent process to control Notes. Then rerun the Apple "
            "Notes import command."
        )
    if isinstance(exc, FileNotFoundError):
        return "Check that the referenced path exists and is readable."
    return "Fix the input and retry the command."


def _workspace_from_args(args) -> Workspace | None:
    return _runtime_from_args(args, init_default_home=False).workspace


def _runtime_from_args(
    args,
    *,
    require_workspace: bool = False,
    init_default_home: bool = True,
) -> AlcoveRuntime:
    return AlcoveRuntime.resolve(
        workspace=Path(args.workspace) if getattr(args, "workspace", None) else None,
        home=Path(args.home) if getattr(args, "home", None) else None,
        kb=getattr(args, "kb", None),
        require_workspace=require_workspace,
        init_default_home=init_default_home,
    )


def _health_runtime_from_args(args) -> AlcoveRuntime:
    workspace = Path(args.workspace) if getattr(args, "workspace", None) else None
    if workspace is None and not getattr(args, "kb", None) and not getattr(args, "home", None):
        try:
            workspace = Workspace.discover()
        except WorkspaceNotFoundError:
            workspace = None
    return AlcoveRuntime.resolve(
        workspace=workspace,
        home=Path(args.home) if getattr(args, "home", None) else None,
        kb=getattr(args, "kb", None),
        require_workspace=False,
        init_default_home=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2
    try:
        if args.version:
            print(f"alcove {__version__}")
            return 0
        if args.command is None:
            return _argument_error(parser, "the following arguments are required: command")

        def workspace_runtime(value: argparse.Namespace) -> AlcoveRuntime:
            return _runtime_from_args(value, require_workspace=True)

        return dispatch_cli_command(
            args,
            CliDispatchContext(
                parser=parser,
                runtime_from_args=_runtime_from_args,
                workspace_runtime_from_args=workspace_runtime,
                health_runtime_from_args=_health_runtime_from_args,
                workspace_from_args=_workspace_from_args,
                tags_from_args=_tags,
                optional_tags_from_args=_optional_tags,
                refs_from_args=_refs,
                optional_refs_from_args=_optional_refs,
                resources_from_args=_resources,
                optional_resources_from_args=_optional_resources,
                selected_takeaways_from_args=_selected_takeaways,
                routine_schedule_from_args=_routine_schedule_from_args,
                split_csv_values=_split_csv_values,
                print_inbox_post=_print_inbox_post,
                print_path=_print_path,
                print_search_rows=_print_search_rows,
                argument_error=_argument_error,
            ),
        )
    except (AlcoveError, FileExistsError, FileNotFoundError, ValueError) as exc:
        if "args" in locals() and bool(getattr(args, "json", False)):
            print(json.dumps(_json_error_payload(args, exc), ensure_ascii=False, indent=2))
        else:
            print(f"alcove: {exc}", file=sys.stderr)
        return 2


def entrypoint() -> None:
    raise SystemExit(main())
