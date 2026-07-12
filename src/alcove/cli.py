from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from alcove import __version__
from alcove.application import AlcoveApplication
from alcove.automations import AutomationsModule
from alcove.blog_monitor import BlogMonitorModule
from alcove.connectors.apple_notes import AppleNotesImportRequest, AppleNotesLocalImportRequest
from alcove.connectors.chrome_bookmarks import (
    ChromeBookmarksImportRequest,
    ChromeBookmarksLocalImportRequest,
)
from alcove.connectors.github_stars import GitHubStarsImportRequest, GitHubStarsUrlImportRequest
from alcove.dashboard import DashboardModule, serve_dashboard
from alcove.errors import AlcoveError, WorkspaceNotFoundError
from alcove.home import AlcoveHome, KnowledgeBaseRecord
from alcove.inbox_models import InboxNoteRequest
from alcove.knowledge import (
    AddConceptRequest,
    AddEntityRequest,
    AddQuestionRequest,
    NoteSourceRequest,
    ReviseKnowledgeRequest,
)
from alcove.linking import LinkSourceRequest
from alcove.mcp_server import run_mcp_server
from alcove.mounts import AddMountRequest
from alcove.paths import compact_user_path
from alcove.pins import AddPinRequest, UpdatePinRequest
from alcove.projects import AddProjectRequest
from alcove.prompts import AddPromptRequest
from alcove.publishers import PublisherModule
from alcove.profile_installer import ProfileInstaller
from alcove.runtime import AlcoveRuntime
from alcove.search import SearchRequest
from alcove.service import ServiceModule
from alcove.tasks import AddIdeaRequest, AddRoutineRequest, AddTaskRequest
from alcove.usage import UsageRecorder
from alcove.watchers import WatcherModule
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
    service_tick.add_argument("--skip-health-fix", action="store_true")
    service_tick.add_argument("--today", default="")
    service_tick.add_argument("--json", action="store_true")

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
    automation_import = automation_sub.add_parser(
        "import-social-radar", help="Import legacy Social Radar automation jobs"
    )
    automation_import.add_argument("--home", default=argparse.SUPPRESS)
    automation_import.add_argument("source_home", nargs="?", default="~/.social_radar")
    automation_import.add_argument("--json", action="store_true")

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
    radar_import = radar_sub.add_parser(
        "import-social-radar", help="Import legacy Social Radar data"
    )
    radar_import.add_argument("source_home", nargs="?", default="~/.social_radar")
    radar_import.add_argument("--home", default=argparse.SUPPRESS)
    radar_import.add_argument("--force", action="store_true")
    radar_import.add_argument("--json", action="store_true")
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
    prompt_save.add_argument("title")
    prompt_save.add_argument("--content", required=True)
    prompt_save.add_argument("--description", default="")
    prompt_save.add_argument("--tag", action="append", default=[])
    prompt_save.add_argument("--tags", default="")
    prompt_save.add_argument("--use-case", action="append", default=[])
    prompt_save.add_argument("--use-cases", default="")
    prompt_save.add_argument("--source-ref", action="append", default=[])
    prompt_save.add_argument("--source-refs", default="")
    prompt_save.add_argument("--json", action="store_true")
    prompt_search = prompt_sub.add_parser("search", help="Search reusable global prompts")
    prompt_search.add_argument("query", nargs="?", default="")
    prompt_search.add_argument("--tag", default="")
    prompt_search.add_argument("--status", default="active")
    prompt_search.add_argument("--json", action="store_true")
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
    import_social_radar = task_sub.add_parser(
        "import-social-radar",
        help="Import todos, ideas, and routines from a Social Radar todos.json file",
    )
    import_social_radar.add_argument("--source", default="~/.social_radar/data/todos.json")
    import_social_radar.add_argument("--json", action="store_true")

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
    mount_add.add_argument("--json", action="store_true")
    mount_list = mount_sub.add_parser("list", help="List mounts")
    mount_list.add_argument("--status", default="active")
    mount_list.add_argument("--json", action="store_true")
    mount_scan = mount_sub.add_parser("scan", help="Scan mounted sources")
    mount_scan.add_argument("mount_id", nargs="?")
    mount_scan.add_argument("--include-diagnostics", action="store_true")
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


def _tags(args) -> list[str]:
    return [*getattr(args, "tag", []), *_split_csv(getattr(args, "tags", ""))]


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
        *_split_csv(getattr(args, "source_refs", "")),
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


def _connector_cli_report(
    report: dict,
    *,
    include_items: bool,
    include_diff: bool = False,
) -> dict:
    payload = dict(report)
    _move_connector_storage_paths(payload)
    items = payload.get("items")
    if isinstance(items, list):
        payload["item_count"] = len(items)
        if not include_items:
            payload.pop("items", None)
    _summarize_diff_payload(payload, include_diff=include_diff)
    for source in payload.get("sources", []):
        if isinstance(source, dict):
            _move_connector_storage_paths(source)
            _summarize_diff_payload(source, include_diff=include_diff)
    return payload


def _move_connector_storage_paths(payload: dict) -> None:
    for key in ["export_file", "export_dir", "index_path", "source_file"]:
        if key in payload:
            payload.pop(key)


def _connector_storage_path(payload: dict, key: str) -> object:
    if key in payload:
        return payload[key]
    debug = payload.get("debug") if isinstance(payload.get("debug"), dict) else {}
    storage = debug.get("storage") if isinstance(debug.get("storage"), dict) else {}
    return storage.get(key, "")


def _summarize_diff_payload(payload: dict, *, include_diff: bool) -> None:
    diff = payload.get("diff")
    if include_diff or not isinstance(diff, dict):
        return
    payload["diff_summary"] = {
        "added_count": len(diff.get("added") or []),
        "removed_count": len(diff.get("removed") or []),
        "updated_count": len(diff.get("updated") or []),
        "unchanged": int(diff.get("unchanged") or 0),
    }
    payload.pop("diff", None)


def _kb_dict(record: KnowledgeBaseRecord) -> dict:
    return {
        "name": record.name,
        "path": compact_user_path(record.path),
        "config_path": compact_user_path(record.config_path),
    }


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
        return "Check macOS Notes automation permissions, osascript availability, or the Apple Notes export directory."
    if isinstance(exc, FileNotFoundError):
        return "Check that the referenced path exists and is readable."
    return "Fix the input and retry the command."


def _print_install_result(result: dict) -> None:
    if result.get("profile"):
        print(f"profile: {result['profile']}")
    if result.get("home"):
        print(f"home: {result['home']}")
    if result.get("kb"):
        print(f"kb: {result['kb']}")
    if result.get("path"):
        print(f"path: {result['path']}")
    if result.get("workspace"):
        print(f"workspace: {result['workspace']}")
    for file in result.get("files", []):
        action = file.get("action")
        if action is None:
            action = "installed" if file.get("installed") else "not_found"
        target = file.get("target") or "file"
        print(f"{target} | {action} | {file['path']}")


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
        if args.command == "doctor":
            runtime = _runtime_from_args(args, require_workspace=True)
            report = AlcoveApplication(runtime).system.doctor_payload()
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                for check in report["checks"]:
                    print(f"{check['status']} | {check['name']} | {check.get('message', '')}")
            return 1 if report["status"] == "issues" else 0
        if args.command == "health":
            runtime = _health_runtime_from_args(args)
            report = AlcoveApplication(runtime).system.health_payload(
                fix=args.fix,
                strict=args.strict,
                deep=args.deep,
                refresh_stale_connectors=args.refresh_stale_connectors,
                refresh_all_connectors=args.refresh_all_connectors,
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
        if args.command == "install":
            runtime = _runtime_from_args(args, require_workspace=True)
            result = AlcoveApplication(runtime).system.install_payload(
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
                _print_install_result(result)
            return 0
        if args.command == "home":
            if args.home_command == "init":
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
            return _argument_error(parser, "the following arguments are required: home_command")
        if args.command == "okf":
            runtime = AlcoveRuntime.resolve(home=args.home)
            app = AlcoveApplication(runtime)
            if args.okf_command == "catalog" and args.okf_catalog_command == "build":
                payload = app.system.okf_catalog_build_payload(
                    include_all_status=args.include_all_status
                )
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    print(f"okf catalog: {payload['root']} | files: {len(payload['files'])}")
                return 0
            return _argument_error(parser, "the following arguments are required: okf_command")
        if args.command == "usage":
            home = AlcoveHome.init(Path(args.home)) if args.home else AlcoveHome.init()
            recorder = UsageRecorder(home)
            if args.usage_command == "summary":
                payload = recorder.write_rollups()
            elif args.usage_command == "prune":
                payload = recorder.prune(retention_days=args.days, now=args.now or None)
            else:
                return _argument_error(
                    parser, "the following arguments are required: usage_command"
                )
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        if args.command == "service":
            home = AlcoveHome.init(Path(args.home)) if args.home else AlcoveHome.init()
            service_module = ServiceModule(home)
            dashboard = bool(getattr(args, "dashboard", False))
            scheduler = bool(getattr(args, "scheduler", False))
            if args.service_command == "install":
                service_payload = service_module.install(
                    dashboard=dashboard,
                    scheduler=scheduler,
                    host=args.host,
                    port=args.port,
                    interval_minutes=args.interval_minutes,
                    load=args.load,
                )
            elif args.service_command == "uninstall":
                service_payload = service_module.uninstall(
                    dashboard=dashboard,
                    scheduler=scheduler,
                    unload=args.unload,
                )
            elif args.service_command == "status":
                service_payload = service_module.status(dashboard=dashboard, scheduler=scheduler)
            elif args.service_command == "start":
                service_payload = service_module.start(dashboard=dashboard, scheduler=scheduler)
            elif args.service_command == "stop":
                service_payload = service_module.stop(dashboard=dashboard, scheduler=scheduler)
            elif args.service_command == "restart":
                service_module.stop(dashboard=dashboard, scheduler=scheduler)
                service_payload = service_module.start(dashboard=dashboard, scheduler=scheduler)
                service_payload["status"] = "restarted"
            elif args.service_command == "tick":
                service_payload = service_module.tick(
                    retention_days=args.retention_days,
                    refresh_connectors=not args.skip_connectors,
                    check_watchers=not args.skip_watchers,
                    check_blogs=not args.skip_blogs,
                    check_radars=not args.skip_radars,
                    run_automations=not args.skip_automations,
                    run_publishers=not args.skip_publishers,
                    fix_health=not args.skip_health_fix,
                    today=args.today,
                )
            else:
                return _argument_error(
                    parser, "the following arguments are required: service_command"
                )
            if args.json:
                print(json.dumps(service_payload, ensure_ascii=False, indent=2))
            else:
                print(json.dumps(service_payload, ensure_ascii=False, indent=2))
            return 0
        if args.command == "automation":
            home = AlcoveHome.init(Path(args.home)) if args.home else AlcoveHome.init()
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
            elif args.automation_command == "import-social-radar":
                payload = automations.import_social_radar(args.source_home)
            else:
                return _argument_error(
                    parser, "the following arguments are required: automation_command"
                )
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        if args.command == "publish":
            home = AlcoveHome.init(Path(args.home)) if args.home else AlcoveHome.init()
            publishers = PublisherModule(home)
            if args.publish_command == "init":
                if args.publisher != "apple-notes":
                    return _argument_error(parser, "supported publisher: apple-notes")
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
                return _argument_error(
                    parser, "the following arguments are required: publish_command"
                )
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        if args.command == "watch":
            home = AlcoveHome.init(Path(args.home)) if args.home else AlcoveHome.init()
            watcher_module = WatcherModule(home)
            if args.watch_command == "add":
                watch_payload = watcher_module.add(
                    title=args.title,
                    url=args.url,
                    kind=args.kind,
                    kb=args.kb,
                    tags=_tags(args),
                    ttl_hours=args.ttl_hours,
                )
            elif args.watch_command == "list":
                watch_payload = watcher_module.list_sources(status=args.status)
            elif args.watch_command == "check":
                watch_payload = watcher_module.check(
                    source_id=args.source_id, stale_only=args.stale
                )
            else:
                return _argument_error(
                    parser, "the following arguments are required: watch_command"
                )
            if args.json:
                print(json.dumps(watch_payload, ensure_ascii=False, indent=2))
            else:
                print(json.dumps(watch_payload, ensure_ascii=False, indent=2))
            return 0
        if args.command == "blog":
            home = AlcoveHome.init(Path(args.home)) if args.home else AlcoveHome.init()
            blog_module = BlogMonitorModule(home)
            if args.blog_command == "add":
                blog_payload = blog_module.add(
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
                    tags=_tags(args),
                    ttl_hours=args.ttl_hours,
                )
            elif args.blog_command == "list":
                blog_payload = blog_module.list_sources(status=args.status)
            elif args.blog_command == "seed":
                blog_payload = blog_module.seed(source_id=args.source_id)
            elif args.blog_command == "check":
                blog_payload = blog_module.check(
                    source_id=args.source_id,
                    stale_only=args.stale,
                    capture_override=False if args.no_capture else None,
                    summary_override=True if args.summary else None,
                    notify_override=True if args.notify else None,
                )
            else:
                return _argument_error(parser, "the following arguments are required: blog_command")
            if args.json:
                print(json.dumps(blog_payload, ensure_ascii=False, indent=2))
            else:
                print(json.dumps(blog_payload, ensure_ascii=False, indent=2))
            return 0
        if args.command == "radar":
            from alcove.radars import RadarModule

            home = AlcoveHome.init(Path(args.home)) if args.home else AlcoveHome.init()
            radar_module = RadarModule(home)
            if args.radar_command == "list":
                radar_payload = radar_module.list(status=args.status)
            elif args.radar_command == "init":
                if not args.from_preset:
                    return _argument_error(
                        parser, "--from-preset is required for radar init in this release"
                    )
                radar_payload = radar_module.init_from_preset(
                    args.from_preset, args.radar_id, force=args.force
                )
            elif args.radar_command == "run":
                radar_payload = radar_module.run(
                    args.radar_id,
                    skip_fetch=args.skip_fetch,
                    force=args.force,
                    ai=args.ai,
                    notify=args.notify,
                )
            elif args.radar_command == "status":
                radar_payload = radar_module.status(args.radar_id)
            elif args.radar_command == "import-social-radar":
                radar_payload = radar_module.import_social_radar(
                    args.source_home,
                    force=args.force,
                )
            elif args.radar_command == "preset":
                if args.radar_preset_command != "list":
                    return _argument_error(
                        parser, "the following arguments are required: radar_preset_command"
                    )
                radar_payload = radar_module.preset_list()
            else:
                return _argument_error(
                    parser, "the following arguments are required: radar_command"
                )
            if args.json:
                print(json.dumps(radar_payload, ensure_ascii=False, indent=2))
            else:
                print(json.dumps(radar_payload, ensure_ascii=False, indent=2))
            return 0
        if args.command == "hub":
            home = AlcoveHome.init(Path(args.home)) if args.home else AlcoveHome.init()
            profiles = ProfileInstaller(home)
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
                return _argument_error(parser, "the following arguments are required: hub_command")
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                _print_install_result(result)
            return 0
        if args.command == "global":
            runtime = _runtime_from_args(args)
            if args.global_command == "install":
                result = AlcoveApplication(runtime).system.global_install_payload(
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
                    _print_install_result(result)
                return 0
            return _argument_error(parser, "the following arguments are required: global_command")
        if args.command == "kb":
            home = AlcoveHome.init(Path(args.home)) if args.home else AlcoveHome.init()
            if args.kb_command == "add":
                record = home.register_knowledge_base(args.name, args.path)
                payload = {"status": "registered", "knowledge_base": _kb_dict(record)}
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    print(f"knowledge_base: {record.name} | {record.path}")
                return 0
            if args.kb_command == "list":
                records = [_kb_dict(record) for record in home.list_knowledge_bases()]
                if args.json:
                    print(json.dumps(records, ensure_ascii=False, indent=2))
                else:
                    for record in records:
                        print(f"{record['name']} | {record['path']}")
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
                if args.json:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    _print_install_result(result)
                return 0
            return _argument_error(parser, "the following arguments are required: kb_command")
        if args.command == "inbox":
            runtime = _runtime_from_args(args, require_workspace=True)
            app = AlcoveApplication(runtime)
            if args.inbox_command == "peek":
                post = app.inbox.inbox_peek_payload()["item"]
                if post is None:
                    if args.json:
                        print(json.dumps({"error": "inbox empty"}, ensure_ascii=False))
                    else:
                        print("Inbox is empty.")
                else:
                    if args.json:
                        print(json.dumps(post, ensure_ascii=False, default=str))
                    else:
                        _print_inbox_post(post)
                return 0
            if args.inbox_command == "read":
                post = app.inbox.inbox_read_payload(args.name)["item"]
                if args.json:
                    print(json.dumps(post, ensure_ascii=False, default=str))
                else:
                    _print_inbox_post(post)
                return 0
            if args.inbox_command == "classify":
                draft = app.inbox.inbox_classify_payload(args.name, args.topic)
                print(json.dumps(draft, ensure_ascii=False, default=str))
                return 0
            if args.inbox_command == "archive":
                payload = app.inbox.inbox_archive_payload(
                    args.name,
                    args.topic,
                    summary=args.summary,
                    tags=_tags(args) or None,
                    no_auto_tags=args.no_auto_tags,
                    supersede_similar=args.supersede_similar,
                    validate=args.validate,
                )
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False, default=str))
                else:
                    _print_path("archive", Path(payload["archive"]))
                    _print_path("source", Path(payload["source"]))
                    print(f"tags: {','.join(payload['tags'])}")
                return 0
            if args.inbox_command == "note":
                payload = app.inbox.inbox_note_payload(
                    InboxNoteRequest(
                        name=args.name,
                        topic=args.topic,
                        summary=args.summary,
                        tags=_tags(args),
                        selected_takeaways=_selected_takeaways(args.selected_takeaways),
                        why=args.why,
                        connection=args.connection,
                        action=args.action,
                        personal_note=args.personal_note,
                        no_auto_tags=args.no_auto_tags,
                        supersede_similar=args.supersede_similar,
                    ),
                    validate=args.validate,
                )
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False, default=str))
                else:
                    _print_path("archive", Path(payload["archive"]))
                    _print_path("source", Path(payload["source"]))
                    _print_path("concept", Path(payload["concept"]) if payload["concept"] else None)
                    print(f"tags: {','.join(payload['tags'])}")
                return 0
            if args.inbox_command == "manual-add":
                payload = app.inbox.inbox_manual_add_payload(
                    title=args.title,
                    content=args.content,
                    source=args.source,
                )
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"inbox: {payload['id']} | {payload['path']}")
                return 0
            if args.inbox_command == "todo":
                print(
                    json.dumps(
                        app.inbox.inbox_todo_payload(args.name, args.reason), ensure_ascii=False
                    )
                )
                return 0
            if args.inbox_command == "delete":
                print(
                    json.dumps(
                        app.inbox.inbox_delete_payload(args.name, confirm=args.confirm),
                        ensure_ascii=False,
                    )
                )
                return 0
            return _argument_error(parser, "the following arguments are required: inbox_command")
        if args.command == "knowledge":
            runtime = _runtime_from_args(args, require_workspace=True)
            app = AlcoveApplication(runtime)
            if args.knowledge_command == "note-source":
                payload = app.knowledge.note_source_payload(
                    NoteSourceRequest(
                        platform=args.platform,
                        title=args.title,
                        topic=args.topic,
                        resource=args.resource,
                        summary=args.summary,
                        tags=args.tag,
                    )
                )
                _print_path("source", Path(payload["source_path"]))
                _print_path(
                    "concept",
                    Path(payload["concept_path"]) if payload["concept_path"] else None,
                )
                return 0
            if args.knowledge_command == "add-note":
                payload = app.knowledge.knowledge_add_concept_payload(
                    AddConceptRequest(
                        topic=args.topic,
                        title=args.title,
                        summary=args.summary,
                        tags=_tags(args),
                    )
                )
                print(json.dumps(payload, ensure_ascii=False))
                return 0
            if args.knowledge_command == "revise":
                payload = app.knowledge.knowledge_revise_payload(
                    ReviseKnowledgeRequest(
                        path=args.path,
                        summary=args.summary,
                        answer=args.answer,
                        append=args.append,
                        tags=_tags(args),
                        source_refs=_refs(args),
                        reason=args.reason,
                        status=args.status,
                    )
                )
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    _print_path("revised", Path(payload["path"]))
                return 0
            if args.knowledge_command == "delete":
                payload = app.knowledge.knowledge_delete_payload(
                    args.path,
                    confirm=args.confirm,
                    reason=args.reason,
                )
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
                elif payload["status"] == "preview":
                    print(
                        "delete preview: "
                        f"{payload['type']} | {payload['title']} | {payload['path']}"
                    )
                    print("rerun with --confirm to mark this knowledge item as deleted")
                else:
                    print(f"deleted: {payload['path']}")
                return 0
            if args.knowledge_command == "add-question":
                payload = app.knowledge.knowledge_add_question_payload(
                    AddQuestionRequest(
                        topic=args.topic,
                        question=args.question,
                        answer=args.answer,
                        tags=_tags(args),
                        source_refs=_refs(args),
                    )
                )
                print(json.dumps(payload, ensure_ascii=False))
                return 0
            if args.knowledge_command == "add-entity":
                payload = app.knowledge.knowledge_add_entity_payload(
                    AddEntityRequest(
                        topic=args.topic,
                        name=args.name,
                        kind=args.kind,
                        summary=args.summary,
                        use_cases=args.use_cases,
                        open_questions=args.open_questions,
                        tags=_tags(args),
                        source_refs=_refs(args),
                    )
                )
                print(json.dumps(payload, ensure_ascii=False))
                return 0
            if args.knowledge_command == "promote":
                payload = app.knowledge.knowledge_promote_payload(
                    args.source,
                    topic=args.topic,
                    summary=args.summary,
                )
                print(json.dumps(payload, ensure_ascii=False))
                return 0
            if args.knowledge_command == "refresh":
                result = app.knowledge.knowledge_refresh_payload(
                    args.topic,
                    in_place=args.in_place,
                    summary=args.summary,
                )
                print(json.dumps(result, ensure_ascii=False, default=str))
                return 0
            if args.knowledge_command == "topics":
                print(json.dumps(app.knowledge.knowledge_topics_payload(), ensure_ascii=False))
                return 0
            return _argument_error(
                parser,
                "the following arguments are required: knowledge_command",
            )
        if args.command == "search":
            runtime = _runtime_from_args(args)
            workspace = runtime.workspace
            app = AlcoveApplication(runtime)
            if args.unindexed:
                if workspace is None:
                    return _argument_error(parser, "search --unindexed requires --workspace")
                issues = app.search.search_unindexed_payload()["issues"]
                if args.json:
                    print(json.dumps({"issues": issues}, ensure_ascii=False, indent=2))
                else:
                    for issue in issues:
                        print(f"{issue['kind']} | {issue['path']} | {issue['message']}")
                return 1 if issues else 0
            if args.tags:
                results = app.search.search_tags_payload()["tags"][: max(args.limit, 0)]
                if args.json:
                    print(json.dumps(results, ensure_ascii=False, indent=2))
                else:
                    for row in results:
                        print(f"{row['tag']} | {row['count']}")
                return 0
            if args.tag_doctor:
                results = app.search.search_tag_doctor_payload()["issues"][: max(args.limit, 0)]
                if args.json:
                    print(json.dumps(results, ensure_ascii=False, indent=2))
                else:
                    for row in results:
                        print(f"{row['canonical']} | {row['count']} | {', '.join(row['variants'])}")
                return 0
            if args.recent is not None:
                results = app.search.search_recent_payload(args.recent)["results"]
            else:
                results = app.search.search(
                    SearchRequest(
                        query=args.query,
                        type_filter=args.type_filter,
                        tag=args.tag,
                        topic=args.topic,
                        platform=args.platform,
                        date_from=args.date_from,
                        date_to=args.date_to,
                        min_confidence=args.min_confidence,
                        status=args.status,
                        limit=args.limit,
                    ),
                    surface="cli",
                )
            if args.json:
                print(json.dumps(results, ensure_ascii=False, indent=2))
            else:
                _print_search_rows(results)
            return 0
        if args.command == "pin":
            runtime = _runtime_from_args(args)
            app = AlcoveApplication(runtime)
            if args.pin_command == "add":
                payload = app.global_home.pin_add_payload(
                    AddPinRequest(
                        title=args.title,
                        description=args.description,
                        summary=args.summary,
                        content=args.content,
                        kind=args.kind,
                        tags=_tags(args),
                        priority=args.priority,
                        source_refs=_refs(args),
                        resources=_resources(args),
                        content_format=args.content_format,
                    )
                )
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    _print_path("pin", Path(payload["path"]))
                return 0
            if args.pin_command == "get":
                payload = app.global_home.pin_get_payload(args.pin_id)
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    pin = payload["pin"]
                    print(f"{pin['priority']} | {pin['kind']} | {pin['status']} | {pin['title']}")
                    if pin.get("summary"):
                        print(pin["summary"])
                    if pin.get("content"):
                        print(pin["content"])
                return 0
            if args.pin_command == "list":
                payload = app.global_home.pin_list_payload(args.tag, args.status)
                results = payload["pins"]
                if args.json:
                    print(json.dumps(results, ensure_ascii=False, indent=2))
                else:
                    for pin in results:
                        print(
                            f"{pin['priority']} | {pin['kind']} | {pin['status']} | {pin['title']} | {pin['path']}"
                        )
                return 0
            if args.pin_command == "search":
                payload = app.global_home.pin_search_payload(
                    query=args.query,
                    kind=args.kind,
                    tag=args.tag,
                    status=args.status,
                )
                results = payload["pins"]
                if args.json:
                    print(json.dumps(results, ensure_ascii=False, indent=2))
                else:
                    for pin in results:
                        print(
                            f"{pin['priority']} | {pin['kind']} | {pin['status']} | {pin['title']} | {pin['path']}"
                        )
                return 0
            if args.pin_command == "update":
                payload = app.global_home.pin_update_payload(
                    UpdatePinRequest(
                        pin_id=args.pin_id,
                        title=args.title,
                        description=args.description,
                        summary=args.summary,
                        content=args.content,
                        kind=args.kind,
                        tags=_optional_tags(args),
                        priority=args.priority,
                        source_refs=_optional_refs(args),
                        resources=_optional_resources(args),
                        status=args.status,
                        content_format=args.content_format,
                    )
                )
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"{payload['status']}: {payload['path']}")
                return 0
            if args.pin_command == "rebuild-index":
                payload = app.global_home.pin_rebuild_index_payload()
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"{payload['status']}: {payload['index_path']}")
                return 0
            if args.pin_command == "render-html":
                payload = app.global_home.pin_render_html_payload(args.output)
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"{payload['status']}: {payload['path']}")
                return 0
            if args.pin_command == "archive":
                payload = app.global_home.pin_archive_payload(args.pin_id, confirm=args.confirm)
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"{payload['status']}: {payload['path']}")
                return 0
            return _argument_error(parser, "the following arguments are required: pin_command")
        if args.command == "project":
            runtime = _runtime_from_args(args)
            app = AlcoveApplication(runtime)
            if args.project_command == "add":
                payload = app.global_home.project_add_payload(
                    AddProjectRequest(alias=args.alias, path=args.path, note=args.note)
                )
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"project: {payload['project']['alias']} | {payload['project']['path']}")
                return 0
            if args.project_command == "get":
                payload = app.global_home.project_get_payload(args.alias)
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    project = payload["project"]
                    print(f"{project['alias']} | {project['path']} | {project['note']}")
                return 0
            if args.project_command == "find":
                payload = app.global_home.project_find_payload(args.keyword)
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    for project in payload["projects"]:
                        print(f"{project['source']} | {project['alias']} | {project['path']}")
                return 0
            if args.project_command == "list":
                payload = app.global_home.project_list_payload()
                if args.json:
                    print(json.dumps(payload["projects"], ensure_ascii=False, indent=2))
                else:
                    for project in payload["projects"]:
                        print(f"{project['alias']} | {project['path']} | {project['note']}")
                return 0
            if args.project_command == "remove":
                payload = app.global_home.project_remove_payload(args.alias)
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"{payload['status']}: {args.alias}")
                return 0
            if args.project_command == "roots-set":
                payload = app.global_home.project_roots_set_payload(args.roots)
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    print("roots: " + ", ".join(payload["roots"]))
                return 0
            return _argument_error(parser, "the following arguments are required: project_command")
        if args.command == "prompt":
            runtime = _runtime_from_args(args)
            app = AlcoveApplication(runtime)
            if args.prompt_command == "save":
                payload = app.global_home.prompt_save_payload(
                    AddPromptRequest(
                        title=args.title,
                        content=args.content,
                        description=args.description,
                        tags=_tags(args),
                        use_cases=args.use_case + _split_csv(args.use_cases),
                        source_refs=_refs(args),
                    )
                )
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"prompt: {payload['prompt']['id']} | {payload['path']}")
                return 0
            if args.prompt_command == "search":
                payload = app.global_home.prompt_search_payload(
                    query=args.query,
                    tag=args.tag,
                    status=args.status,
                )
                if args.json:
                    print(json.dumps(payload["prompts"], ensure_ascii=False, indent=2))
                else:
                    for prompt in payload["prompts"]:
                        print(f"{prompt['status']} | {prompt['title']} | {prompt['id']}")
                return 0
            if args.prompt_command == "get":
                payload = app.global_home.prompt_get_payload(args.prompt_id)
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    prompt = payload["prompt"]
                    print(f"# {prompt['title']}\n\n{prompt['content']}")
                return 0
            if args.prompt_command == "archive":
                payload = app.global_home.prompt_archive_payload(
                    args.prompt_id,
                    confirm=args.confirm,
                )
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"{payload['status']}: {payload['path']}")
                return 0
            if args.prompt_command == "tags":
                payload = app.global_home.prompt_tags_payload()
                if args.json:
                    print(json.dumps(payload["tags"], ensure_ascii=False, indent=2))
                else:
                    for tag in payload["tags"]:
                        print(f"{tag['tag']} | {tag['count']}")
                return 0
            if args.prompt_command == "rebuild-index":
                payload = app.global_home.prompt_rebuild_index_payload()
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    print(f"index: {payload['index_path']} | prompts: {payload['count']}")
                return 0
            return _argument_error(parser, "the following arguments are required: prompt_command")
        if args.command == "idea":
            runtime = _runtime_from_args(args)
            app = AlcoveApplication(runtime)
            if args.idea_command == "add":
                payload = app.global_home.idea_add_payload(
                    AddIdeaRequest(
                        title=args.title,
                        notes=args.notes,
                        tags=_tags(args),
                    )
                )
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"idea: {payload['idea']['id']}")
                return 0
            if args.idea_command == "list":
                payload = app.global_home.idea_list_payload(args.status)
                results = payload["ideas"]
                if args.json:
                    print(json.dumps(results, ensure_ascii=False, indent=2))
                else:
                    for idea in results:
                        print(f"{idea['status']} | {idea['title']} | {idea['id']}")
                return 0
            if args.idea_command == "promote":
                payload = app.global_home.idea_promote_payload(
                    args.idea_id,
                    priority=args.priority,
                    due=args.due,
                    notes=args.notes,
                )
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"task: {payload['task']['id']}")
                return 0
            if args.idea_command == "edit":
                payload = app.global_home.idea_edit_payload(
                    args.idea_id,
                    title=args.title,
                    notes=args.notes,
                    tags=_optional_tags(args),
                )
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"idea: {payload['idea']['id']}")
                return 0
            if args.idea_command == "archive":
                payload = app.global_home.idea_archive_payload(args.idea_id)
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"idea: {payload['idea']['id']}")
                return 0
            if args.idea_command == "promote-routine":
                payload = app.global_home.idea_promote_routine_payload(
                    args.idea_id,
                    priority=args.priority,
                    next_due=args.next_due,
                    notes=args.notes,
                    schedule=_routine_schedule_from_args(args, include_default=True),
                )
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"routine: {payload['routine']['id']}")
                return 0
            return _argument_error(parser, "the following arguments are required: idea_command")
        if args.command == "task":
            runtime = _runtime_from_args(args)
            app = AlcoveApplication(runtime)
            if args.task_command == "add":
                payload = app.global_home.task_add_payload(
                    AddTaskRequest(
                        title=args.title,
                        notes=args.notes,
                        tags=_tags(args),
                        priority=args.priority,
                        due=args.due,
                    )
                )
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"task: {payload['task']['id']}")
                return 0
            if args.task_command == "list":
                payload = app.global_home.task_list_payload(args.status)
                results = payload["tasks"]
                if args.json:
                    print(json.dumps(results, ensure_ascii=False, indent=2))
                else:
                    for task in results:
                        print(
                            f"{task['priority']} | {task['status']} | "
                            f"{task['title']} | {task['id']}"
                        )
                return 0
            if args.task_command == "edit":
                payload = app.global_home.task_edit_payload(
                    args.task_id,
                    title=args.title,
                    notes=args.notes,
                    tags=_optional_tags(args),
                    priority=args.priority,
                    due=args.due,
                )
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"task: {payload['task']['id']}")
                return 0
            if args.task_command == "complete":
                payload = app.global_home.task_complete_payload(args.task_id)
                print(
                    json.dumps(payload, ensure_ascii=False) if args.json else payload["task"]["id"]
                )
                return 0
            if args.task_command == "cancel":
                payload = app.global_home.task_cancel_payload(args.task_id)
                print(
                    json.dumps(payload, ensure_ascii=False) if args.json else payload["task"]["id"]
                )
                return 0
            if args.task_command == "routine-add":
                payload = app.global_home.routine_add_payload(
                    AddRoutineRequest(
                        title=args.title,
                        notes=args.notes,
                        tags=_tags(args),
                        priority=args.priority,
                        every_days=args.every_days,
                        next_due=args.next_due,
                        schedule=_routine_schedule_from_args(args),
                    )
                )
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"routine: {payload['routine']['id']}")
                return 0
            if args.task_command == "routine-list":
                payload = app.global_home.routine_list_payload(args.status)
                results = payload["routines"]
                if args.json:
                    print(json.dumps(results, ensure_ascii=False, indent=2))
                else:
                    for routine in results:
                        print(
                            f"{routine['priority']} | {routine['status']} | "
                            f"{routine['next_due']} | {routine['title']} | {routine['id']}"
                        )
                return 0
            if args.task_command == "routine-edit":
                payload = app.global_home.routine_edit_payload(
                    args.routine_id,
                    title=args.title,
                    notes=args.notes,
                    tags=_optional_tags(args),
                    priority=args.priority,
                    schedule=_routine_schedule_from_args(args) or None,
                    next_due=args.next_due,
                )
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"routine: {payload['routine']['id']}")
                return 0
            if args.task_command == "routine-pause":
                payload = app.global_home.routine_pause_payload(args.routine_id)
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"routine: {payload['routine']['id']}")
                return 0
            if args.task_command == "routine-resume":
                payload = app.global_home.routine_resume_payload(args.routine_id, today=args.today)
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"routine: {payload['routine']['id']}")
                return 0
            if args.task_command == "routine-archive":
                payload = app.global_home.routine_archive_payload(args.routine_id)
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"routine: {payload['routine']['id']}")
                return 0
            if args.task_command == "materialize-due":
                payload = app.global_home.routine_materialize_due_payload(args.today)
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"created: {len(payload['created'])}")
                return 0
            if args.task_command == "digest":
                payload = app.global_home.task_digest_payload(
                    period=args.period,
                    today=args.today,
                    notify=args.notify,
                )
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(payload["text"])
                return 0
            if args.task_command == "import-social-radar":
                payload = app.global_home.task_import_social_radar_payload(args.source)
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    print(
                        "imported social-radar: "
                        f"{payload['tasks']['imported']} tasks, "
                        f"{payload['ideas']['imported']} ideas, "
                        f"{payload['routines']['imported']} routines"
                    )
                return 0
            return _argument_error(parser, "the following arguments are required: task_command")
        if args.command == "mount":
            runtime = _runtime_from_args(args)
            app = AlcoveApplication(runtime)
            if args.mount_command == "add":
                payload = app.external.mount_add_payload(
                    AddMountRequest(
                        path=args.path,
                        name=args.name,
                        mount_type=args.type,
                        tags=_tags(args),
                    )
                )
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"mount: {payload['mount']['id']}")
                return 0
            if args.mount_command == "list":
                payload = app.external.mount_list_payload(args.status)
                results = payload["mounts"]
                if args.json:
                    print(json.dumps(results, ensure_ascii=False, indent=2))
                else:
                    for mount in results:
                        print(f"{mount['type']} | {mount['name']} | {mount['path']}")
                return 0
            if args.mount_command == "scan":
                report = app.external.mount_scan_payload(
                    args.mount_id,
                    include_diagnostics=args.include_diagnostics,
                )
                if args.json:
                    print(json.dumps(report, ensure_ascii=False, indent=2))
                else:
                    print(f"scanned: {report['scanned']}, skipped: {report['skipped']}")
                return 0
            return _argument_error(parser, "the following arguments are required: mount_command")
        if args.command == "connector":
            runtime = _runtime_from_args(args)
            app = AlcoveApplication(runtime)
            if args.connector_command == "status":
                payload = app.external.connector_status_payload(args.connector)
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    for source in payload["sources"]:
                        print(
                            f"{source['connector']}/{source['id']} | {source['status']} | "
                            f"{source['item_count']} items | checked: {source['checked_at']}"
                        )
                return 0
            if args.connector_command == "refresh":
                payload = app.external.connector_refresh_payload(
                    connector=args.connector,
                    stale_only=not args.all,
                )
                if args.json:
                    print(
                        json.dumps(
                            _connector_cli_report(
                                payload,
                                include_items=False,
                                include_diff=args.include_diff,
                            ),
                            ensure_ascii=False,
                            indent=2,
                        )
                    )
                else:
                    print(f"refreshed: {payload['refreshed']}, skipped: {payload['skipped']}")
                return 0
            if args.connector_command == "fetch":
                payload = app.external.connector_fetch_payload(args.item_path)
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    print(
                        f"{payload['connector']} | {payload['relative_path']} | {payload['item']['title']}"
                    )
                return 0
            if args.connector_command == "apple-notes":
                if args.apple_notes_command == "index":
                    report = app.external.apple_notes_index_payload(
                        AppleNotesImportRequest(
                            export_dir=args.export_dir,
                            tags=_tags(args),
                        )
                    )
                    if args.json:
                        print(
                            json.dumps(
                                _connector_cli_report(
                                    report,
                                    include_items=args.include_items,
                                ),
                                ensure_ascii=False,
                                indent=2,
                            )
                        )
                    else:
                        print(f"indexed: {report['scanned']}, skipped: {report['skipped']}")
                    return 0
                if args.apple_notes_command == "import-local":
                    report = app.external.apple_notes_import_local_payload(
                        AppleNotesLocalImportRequest(
                            export_dir=args.export_dir,
                            tags=_tags(args),
                            source_id=args.source_id,
                        )
                    )
                    if args.json:
                        print(
                            json.dumps(
                                _connector_cli_report(
                                    report,
                                    include_items=args.include_items,
                                    include_diff=args.include_diff,
                                ),
                                ensure_ascii=False,
                                indent=2,
                            )
                        )
                    else:
                        export_dir = _connector_storage_path(report, "export_dir")
                        print(
                            f"imported: {report['exported']}, indexed: {report['scanned']}, "
                            f"skipped: {report['skipped']}, export: {export_dir}"
                        )
                    return 0
                if args.apple_notes_command == "refresh":
                    payload = app.external.connector_refresh_payload(
                        connector="apple-notes",
                        stale_only=not args.force,
                        source_id=args.source_id,
                    )
                    if args.json:
                        print(
                            json.dumps(
                                _connector_cli_report(
                                    payload,
                                    include_items=False,
                                    include_diff=args.include_diff,
                                ),
                                ensure_ascii=False,
                                indent=2,
                            )
                        )
                    else:
                        print(f"refreshed: {payload['refreshed']}, skipped: {payload['skipped']}")
                    return 0
                return _argument_error(
                    parser,
                    "the following arguments are required: apple_notes_command",
                )
            if args.connector_command == "github-stars":
                if args.github_stars_command == "index":
                    report = app.external.github_stars_index_payload(
                        GitHubStarsImportRequest(
                            export_file=args.export_file,
                            tags=_tags(args),
                        )
                    )
                    if args.json:
                        print(
                            json.dumps(
                                _connector_cli_report(
                                    report,
                                    include_items=args.include_items,
                                ),
                                ensure_ascii=False,
                                indent=2,
                            )
                        )
                    else:
                        print(f"indexed: {report['scanned']}, skipped: {report['skipped']}")
                    return 0
                if args.github_stars_command == "import-url":
                    report = app.external.github_stars_import_url_payload(
                        GitHubStarsUrlImportRequest(
                            source=args.source,
                            export_file=args.export_file,
                            tags=_tags(args),
                            limit=args.limit,
                            max_pages=args.max_pages,
                        )
                    )
                    if args.json:
                        print(
                            json.dumps(
                                _connector_cli_report(
                                    report,
                                    include_items=args.include_items,
                                    include_diff=args.include_diff,
                                ),
                                ensure_ascii=False,
                                indent=2,
                            )
                        )
                    else:
                        export_file = _connector_storage_path(report, "export_file")
                        print(
                            f"imported: {report['exported']}, indexed: {report['scanned']}, "
                            f"skipped: {report['skipped']}, export: {export_file}"
                        )
                    return 0
                if args.github_stars_command == "refresh":
                    payload = app.external.connector_refresh_payload(
                        connector="github-stars",
                        stale_only=not args.force,
                        source_id=args.source_id,
                    )
                    if args.json:
                        print(
                            json.dumps(
                                _connector_cli_report(
                                    payload,
                                    include_items=False,
                                    include_diff=args.include_diff,
                                ),
                                ensure_ascii=False,
                                indent=2,
                            )
                        )
                    else:
                        print(f"refreshed: {payload['refreshed']}, skipped: {payload['skipped']}")
                    return 0
                return _argument_error(
                    parser,
                    "the following arguments are required: github_stars_command",
                )
            if args.connector_command == "chrome-bookmarks":
                if args.chrome_bookmarks_command == "index":
                    report = app.external.chrome_bookmarks_index_payload(
                        ChromeBookmarksImportRequest(
                            export_file=args.export_file,
                            tags=_tags(args),
                        )
                    )
                    if args.json:
                        print(
                            json.dumps(
                                _connector_cli_report(
                                    report,
                                    include_items=args.include_items,
                                ),
                                ensure_ascii=False,
                                indent=2,
                            )
                        )
                    else:
                        print(f"indexed: {report['scanned']}, skipped: {report['skipped']}")
                    return 0
                if args.chrome_bookmarks_command == "import-local":
                    report = app.external.chrome_bookmarks_import_local_payload(
                        ChromeBookmarksLocalImportRequest(
                            source_file=args.source_file,
                            profile=args.profile,
                            source_id=args.source_id,
                            tags=_tags(args),
                        )
                    )
                    if args.json:
                        print(
                            json.dumps(
                                _connector_cli_report(
                                    report,
                                    include_items=args.include_items,
                                    include_diff=args.include_diff,
                                ),
                                ensure_ascii=False,
                                indent=2,
                            )
                        )
                    else:
                        source_file = _connector_storage_path(report, "source_file")
                        print(
                            f"imported: {report['exported']}, indexed: {report['scanned']}, "
                            f"skipped: {report['skipped']}, source: {source_file}"
                        )
                    return 0
                if args.chrome_bookmarks_command == "refresh":
                    payload = app.external.connector_refresh_payload(
                        connector="chrome-bookmarks",
                        stale_only=not args.force,
                        source_id=args.source_id,
                    )
                    if args.json:
                        print(
                            json.dumps(
                                _connector_cli_report(
                                    payload,
                                    include_items=False,
                                    include_diff=args.include_diff,
                                ),
                                ensure_ascii=False,
                                indent=2,
                            )
                        )
                    else:
                        print(f"refreshed: {payload['refreshed']}, skipped: {payload['skipped']}")
                    return 0
                return _argument_error(
                    parser,
                    "the following arguments are required: chrome_bookmarks_command",
                )
            return _argument_error(
                parser,
                "the following arguments are required: connector_command",
            )
        if args.command == "link":
            runtime = _runtime_from_args(args, require_workspace=True)
            if args.link_command == "source":
                result = AlcoveApplication(runtime).external.link_source_payload(
                    LinkSourceRequest(
                        item_path=args.item_path,
                        topic=args.topic,
                        summary=args.summary,
                        create_concept=args.create_concept,
                    )
                )
                if args.json:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    _print_path("source", Path(result["source_path"]))
                    _print_path(
                        "concept",
                        Path(result["concept_path"]) if result["concept_path"] else None,
                    )
                return 0
            return _argument_error(
                parser,
                "the following arguments are required: link_command",
            )
        if args.command == "export":
            runtime = _runtime_from_args(args)
            if args.export_command == "global":
                result = AlcoveApplication(runtime).system.export_global_payload(args.output_dir)
                if args.json:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    print(f"exported: {result['output_dir']}")
                return 0
            if args.export_command == "kb":
                result = AlcoveApplication(runtime).system.export_kb_payload(
                    args.name, args.output_dir
                )
                if args.json:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    print(f"exported: {result['output_dir']}")
                return 0
            if args.export_command == "all":
                result = AlcoveApplication(runtime).system.export_all_payload(args.output_dir)
                if args.json:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    print(f"exported: {result['output_dir']}")
                return 0
            return _argument_error(
                parser,
                "the following arguments are required: export_command",
            )
        if args.command == "dashboard":
            home = AlcoveHome.init(args.home or None)
            module = DashboardModule(home=home)
            if args.dashboard_command == "build":
                result = module.build(
                    args.output or None,
                    build_frontend=not args.skip_frontend_build,
                )
                if args.json:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    print(f"dashboard: {result['index']}")
                return 0
            if args.dashboard_command == "import-pins":
                result = module.import_pins(
                    regular_file=args.regular_file or None,
                    todo_file=args.todo_file or None,
                )
                if args.json:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    for kind, payload in result.items():
                        if isinstance(payload, dict) and "imported" in payload:
                            print(f"{kind}: {payload['imported']} pins")
                        else:
                            print(f"{kind}: {payload}")
                return 0
            return _argument_error(
                parser,
                "the following arguments are required: dashboard_command",
            )
        if args.command == "serve":
            if args.mcp:
                workspace = _workspace_from_args(args)
                workspace_arg = str(workspace.root) if workspace is not None else "."
                run_mcp_server(workspace_arg, args.home or None, toolset=args.toolset)
                return 0
            if args.dashboard:
                serve_dashboard(
                    AlcoveHome.init(args.home or None),
                    host=args.host,
                    port=args.port,
                )
                return 0
            return _argument_error(parser, "serve requires --mcp or --dashboard")
        if args.command == "validate":
            runtime = _runtime_from_args(args, require_workspace=True)
            issues = AlcoveApplication(runtime).system.validate_payload(
                strict_quality=args.strict_quality
            )["issues"]
            if args.json:
                print(json.dumps({"issues": issues}, ensure_ascii=False, indent=2))
            else:
                for issue in issues:
                    print(f"{issue['kind']} | {issue['path']} | {issue['message']}")
            return 1 if issues else 0
        if args.command == "gardener":
            runtime = _runtime_from_args(args, require_workspace=True)
            payload = AlcoveApplication(runtime).system.gardener_payload(prune=args.prune)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                for issue in payload["issues"]:
                    print(f"{issue['kind']} | {issue['path']} | {issue['message']}")
                for action in payload["actions"]:
                    print(f"{action['action']} | {action['path']}")
            return 0
        return _argument_error(parser, "the following arguments are required: command")
    except (AlcoveError, FileExistsError, FileNotFoundError, ValueError) as exc:
        if "args" in locals() and bool(getattr(args, "json", False)):
            print(json.dumps(_json_error_payload(args, exc), ensure_ascii=False, indent=2))
        else:
            print(f"alcove: {exc}", file=sys.stderr)
        return 2


def entrypoint() -> None:
    raise SystemExit(main())
