from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys
from pathlib import Path

from alcove import __version__
from alcove.classify import ClassifyModule
from alcove.connectors.apple_notes import AppleNotesConnector, AppleNotesImportRequest
from alcove.connectors.github_stars import (
    GitHubStarsConnector,
    GitHubStarsImportRequest,
)
from alcove.doctor import DoctorModule
from alcove.errors import AlcoveError
from alcove.exporter import ExportModule
from alcove.gardener import GardenerModule
from alcove.home import AlcoveHome, KnowledgeBaseRecord
from alcove.inbox import InboxModule, InboxNoteRequest
from alcove.installer import InstallerModule
from alcove.knowledge import (
    AddConceptRequest,
    AddEntityRequest,
    AddQuestionRequest,
    KnowledgeModule,
    NoteSourceRequest,
)
from alcove.lifecycle import LifecycleModule
from alcove.linking import LinkSourceRequest, LinkingModule
from alcove.mcp_server import run_mcp_server
from alcove.mounts import AddMountRequest, MountsModule
from alcove.pins import AddPinRequest, PinsModule
from alcove.profile_installer import ProfileInstaller
from alcove.search import SearchModule, SearchRequest
from alcove.tasks import AddIdeaRequest, AddRoutineRequest, AddTaskRequest, TasksModule
from alcove.validate import ValidateModule
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

    install = sub.add_parser("install", help="Install Alcove MCP config for agents")
    install.add_argument("--home")
    install.add_argument("--workspace")
    install.add_argument("--kb")
    install.add_argument("--target", action="append", default=["all"])
    install.add_argument("--print", dest="print_config", action="store_true")
    install.add_argument("--status", action="store_true")
    install.add_argument("--uninstall", action="store_true")
    install.add_argument("--json", action="store_true")

    home_cmd = sub.add_parser("home", help="Manage Alcove home")
    home_sub = home_cmd.add_subparsers(dest="home_command", required=True)
    home_init = home_sub.add_parser("init", help="Initialize Alcove home")
    home_init.add_argument("--home")
    home_init.add_argument("--json", action="store_true")

    hub = sub.add_parser("hub", help="Manage an Alcove hub workspace")
    hub_sub = hub.add_subparsers(dest="hub_command", required=True)
    hub_init = hub_sub.add_parser("init", help="Initialize a hub workspace")
    hub_init.add_argument("path")
    hub_init.add_argument("--home")
    hub_init.add_argument("--default-kb", default="")
    hub_init.add_argument("--target", action="append", default=["all"])
    hub_init.add_argument("--json", action="store_true")
    hub_install = hub_sub.add_parser("install", help="Install hub entry files")
    hub_install.add_argument("path")
    hub_install.add_argument("--home")
    hub_install.add_argument("--default-kb", default="")
    hub_install.add_argument("--target", action="append", default=["all"])
    hub_install.add_argument("--json", action="store_true")

    global_cmd = sub.add_parser("global", help="Install lightweight global Alcove access")
    global_sub = global_cmd.add_subparsers(dest="global_command", required=True)
    global_install = global_sub.add_parser("install", help="Install global-lite MCP")
    global_install.add_argument("--home")
    global_install.add_argument("--target", action="append", default=["all"])
    global_install.add_argument("--print", dest="print_config", action="store_true")
    global_install.add_argument("--status", action="store_true")
    global_install.add_argument("--uninstall", action="store_true")
    global_install.add_argument("--json", action="store_true")

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
    kb_install.add_argument("--target", action="append", default=["all"])
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
    pin_add.add_argument("--tag", action="append", default=[])
    pin_add.add_argument("--tags", default="")
    pin_add.add_argument("--priority", default="medium")
    pin_add.add_argument("--source-ref", action="append", default=[])
    pin_add.add_argument("--source-refs", default="")
    pin_add.add_argument("--json", action="store_true")
    pin_list = pin_sub.add_parser("list", help="List pinned personal notes")
    pin_list.add_argument("--tag")
    pin_list.add_argument("--status", default="active")
    pin_list.add_argument("--json", action="store_true")
    pin_archive = pin_sub.add_parser("archive", help="Archive a pin")
    pin_archive.add_argument("pin_id")
    pin_archive.add_argument("--confirm", action="store_true")
    pin_archive.add_argument("--json", action="store_true")

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
    routine_add.add_argument("--next-due", required=True)
    routine_add.add_argument("--json", action="store_true")
    routine_list = task_sub.add_parser("routine-list", help="List recurring task templates")
    routine_list.add_argument("--status", default="active")
    routine_list.add_argument("--json", action="store_true")
    materialize_due = task_sub.add_parser("materialize-due", help="Create tasks for due routines")
    materialize_due.add_argument("--today", default="")
    materialize_due.add_argument("--json", action="store_true")

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
    mount_scan.add_argument("--json", action="store_true")

    connector = sub.add_parser("connector", help="Work with external connectors")
    connector.add_argument("--workspace")
    connector.add_argument("--home")
    connector_sub = connector.add_subparsers(dest="connector_command", required=True)
    apple_notes = connector_sub.add_parser("apple-notes", help="Index Apple Notes exports")
    apple_notes_sub = apple_notes.add_subparsers(dest="apple_notes_command", required=True)
    apple_notes_index = apple_notes_sub.add_parser(
        "index", help="Index a deterministic Apple Notes export directory"
    )
    apple_notes_index.add_argument("export_dir")
    apple_notes_index.add_argument("--tag", action="append", default=[])
    apple_notes_index.add_argument("--tags", default="")
    apple_notes_index.add_argument("--json", action="store_true")
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
    github_stars_index.add_argument("--json", action="store_true")

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
    serve.add_argument("--workspace", default="")
    serve.add_argument("--home", default="")
    serve.add_argument("--kb", default="")

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
    return parser


def _print_inbox_post(post) -> None:
    date = post.date or ""
    print(f"{post.platform} | {date} | {post.title}")
    print(f"path: {post.path}")
    print(f"source: {post.source or ''}")
    print(f"content_source: {post.content_source}")
    print()
    print(post.content)


def _print_path(label: str, path: Path | None) -> None:
    if path is not None:
        print(f"{label}: {path}")


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _tags(args) -> list[str]:
    return [*getattr(args, "tag", []), *_split_csv(getattr(args, "tags", ""))]


def _refs(args) -> list[str]:
    return [
        *getattr(args, "source_ref", []),
        *_split_csv(getattr(args, "source_refs", "")),
    ]


def _selected_takeaways(value: str) -> list[str]:
    return [
        item.strip()
        for item in value.replace("，", ",").replace("、", ",").split(",")
        if item.strip()
    ]


def _process_result_dict(result) -> dict:
    return {
        "archive": str(result.archive_path),
        "source": str(result.source_path),
        "concept": str(result.concept_path) if result.concept_path else "",
        "tags": result.tags,
        "confidence": result.confidence,
        "superseded": result.superseded,
    }


def _with_validation(payload: dict, workspace: Workspace, enabled: bool) -> dict:
    if enabled:
        return {**payload, "validation": ValidateModule(workspace).validate()}
    return payload


def _print_search_rows(rows: list[dict]) -> None:
    for row in rows:
        print(
            f"{row.get('date') or '':<10} | "
            f"{row.get('confidence', 0.5):.2f} | "
            f"{row.get('status') or 'active':<10} | "
            f"{row.get('type')} | {row.get('topic')} | "
            f"{row.get('title')} | {row.get('path')}"
        )


def _pin_dict(pin) -> dict:
    return {
        "id": pin.id,
        "title": pin.title,
        "description": pin.description,
        "tags": pin.tags,
        "status": pin.status,
        "priority": pin.priority,
        "source_refs": pin.source_refs,
        "path": str(pin.path),
    }


def _idea_dict(idea) -> dict:
    return {
        "id": idea.id,
        "title": idea.title,
        "notes": idea.notes,
        "tags": idea.tags,
        "status": idea.status,
        "created_at": idea.created_at,
        "updated_at": idea.updated_at,
        "promoted_task_id": idea.promoted_task_id,
    }


def _task_dict(task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "notes": task.notes,
        "tags": task.tags,
        "status": task.status,
        "priority": task.priority,
        "due": task.due,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "completed_at": task.completed_at,
    }


def _kb_dict(record: KnowledgeBaseRecord) -> dict:
    return {
        "name": record.name,
        "path": str(record.path),
        "config_path": str(record.config_path),
    }


def _routine_dict(routine) -> dict:
    return {
        "id": routine.id,
        "title": routine.title,
        "notes": routine.notes,
        "tags": routine.tags,
        "status": routine.status,
        "priority": routine.priority,
        "every_days": routine.every_days,
        "next_due": routine.next_due,
        "created_at": routine.created_at,
        "updated_at": routine.updated_at,
        "last_materialized_due": routine.last_materialized_due,
    }


def _argument_error(parser: argparse.ArgumentParser, message: str) -> int:
    parser.print_usage(sys.stderr)
    print(f"{parser.prog}: error: {message}", file=sys.stderr)
    return 2


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


def _home_from_args(args) -> AlcoveHome | None:
    if getattr(args, "home", None):
        return AlcoveHome.init(Path(args.home))
    return None


def _workspace_from_args(args) -> Workspace | None:
    if getattr(args, "kb", None):
        home = (
            AlcoveHome.init(Path(args.home)) if getattr(args, "home", None) else AlcoveHome.init()
        )
        record = home.get_knowledge_base(args.kb)
        return Workspace.discover(record.path)
    if getattr(args, "workspace", None):
        return Workspace.discover(Path(args.workspace))
    return None


def _required_workspace(parser: argparse.ArgumentParser, args) -> Workspace | int:
    workspace = _workspace_from_args(args)
    if workspace is None:
        return _argument_error(parser, "one of --workspace or --kb is required")
    return workspace


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
            workspace = _required_workspace(parser, args)
            if isinstance(workspace, int):
                return workspace
            report = DoctorModule(workspace).check()
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                for check in report["checks"]:
                    print(f"{check['status']} | {check['name']} | {check.get('message', '')}")
            return 1 if report["status"] == "issues" else 0
        if args.command == "install":
            workspace = _required_workspace(parser, args)
            if isinstance(workspace, int):
                return workspace
            home = AlcoveHome.init(Path(args.home)) if args.home else AlcoveHome.init()
            installer = InstallerModule(workspace, home=home)
            if args.status:
                result = installer.status(args.target)
            elif args.uninstall:
                result = installer.uninstall(args.target, dry_run=args.print_config)
            else:
                result = installer.install(
                    args.target,
                    dry_run=args.print_config,
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
                    "home": str(home.root),
                    "paths": {
                        "config": str(home.paths().config),
                        "knowledge_bases": str(home.paths().knowledge_bases),
                        "pins": str(home.paths().pins),
                        "tasks": str(home.paths().tasks),
                        "mounts": str(home.paths().mounts),
                        "connectors": str(home.paths().connectors),
                    },
                }
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    print(f"Alcove home: {home.root}")
                return 0
            return _argument_error(parser, "the following arguments are required: home_command")
        if args.command == "hub":
            home = AlcoveHome.init(Path(args.home)) if args.home else AlcoveHome.init()
            profiles = ProfileInstaller(home)
            if args.hub_command == "init":
                result = profiles.hub_init(
                    args.path,
                    default_kb=args.default_kb,
                    targets=args.target,
                )
            elif args.hub_command == "install":
                result = profiles.hub_install(
                    args.path,
                    default_kb=args.default_kb,
                    targets=args.target,
                )
            else:
                return _argument_error(parser, "the following arguments are required: hub_command")
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                _print_install_result(result)
            return 0
        if args.command == "global":
            home = AlcoveHome.init(Path(args.home)) if args.home else AlcoveHome.init()
            installer = InstallerModule(None, home=home)
            if args.global_command == "install":
                if args.status:
                    result = installer.status(args.target)
                elif args.uninstall:
                    result = installer.uninstall(args.target, dry_run=args.print_config)
                else:
                    result = installer.install(args.target, dry_run=args.print_config)
                result = {"profile": "global-lite", **result}
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
                result = ProfileInstaller(home).kb_install(
                    args.name,
                    targets=args.target,
                )
                if args.json:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    _print_install_result(result)
                return 0
            return _argument_error(parser, "the following arguments are required: kb_command")
        if args.command == "inbox":
            workspace = _required_workspace(parser, args)
            if isinstance(workspace, int):
                return workspace
            inbox = InboxModule(workspace)
            if args.inbox_command == "peek":
                post = inbox.peek()
                if post is None:
                    if args.json:
                        print(json.dumps({"error": "inbox empty"}, ensure_ascii=False))
                    else:
                        print("Inbox is empty.")
                else:
                    if args.json:
                        print(json.dumps(asdict(post), ensure_ascii=False, default=str))
                    else:
                        _print_inbox_post(post)
                return 0
            if args.inbox_command == "read":
                post = inbox.read(args.name)
                if args.json:
                    print(json.dumps(asdict(post), ensure_ascii=False, default=str))
                else:
                    _print_inbox_post(post)
                return 0
            if args.inbox_command == "classify":
                draft = ClassifyModule(workspace).classify(args.name, args.topic)
                print(json.dumps(asdict(draft), ensure_ascii=False, default=str))
                return 0
            if args.inbox_command == "archive":
                result = inbox.archive(
                    args.name,
                    args.topic,
                    summary=args.summary,
                    tags=_tags(args) or None,
                    no_auto_tags=args.no_auto_tags,
                    supersede_similar=args.supersede_similar,
                )
                payload = _with_validation(_process_result_dict(result), workspace, args.validate)
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False, default=str))
                else:
                    _print_path("archive", result.archive_path)
                    _print_path("source", result.source_path)
                    print(f"tags: {','.join(result.tags)}")
                return 0
            if args.inbox_command == "note":
                result = inbox.note(
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
                    )
                )
                payload = _with_validation(_process_result_dict(result), workspace, args.validate)
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False, default=str))
                else:
                    _print_path("archive", result.archive_path)
                    _print_path("source", result.source_path)
                    _print_path("concept", result.concept_path)
                    print(f"tags: {','.join(result.tags)}")
                return 0
            if args.inbox_command == "manual-add":
                payload = inbox.add_manual(
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
                path = inbox.todo(args.name, args.reason)
                print(json.dumps({"status": "todo", "path": str(path)}, ensure_ascii=False))
                return 0
            if args.inbox_command == "delete":
                print(json.dumps(inbox.delete(args.name, confirm=args.confirm), ensure_ascii=False))
                return 0
            return _argument_error(parser, "the following arguments are required: inbox_command")
        if args.command == "knowledge":
            workspace = _required_workspace(parser, args)
            if isinstance(workspace, int):
                return workspace
            knowledge = KnowledgeModule(workspace)
            if args.knowledge_command == "note-source":
                result = knowledge.note_source(
                    NoteSourceRequest(
                        platform=args.platform,
                        title=args.title,
                        topic=args.topic,
                        resource=args.resource,
                        summary=args.summary,
                        tags=args.tag,
                    )
                )
                _print_path("source", result.source_path)
                _print_path("concept", result.concept_path)
                return 0
            if args.knowledge_command == "add-note":
                result = knowledge.add_concept(
                    AddConceptRequest(
                        topic=args.topic,
                        title=args.title,
                        summary=args.summary,
                        tags=_tags(args),
                    )
                )
                print(
                    json.dumps(
                        {"status": "noted", "okf_concept": str(result.path)},
                        ensure_ascii=False,
                    )
                )
                return 0
            if args.knowledge_command == "add-question":
                result = knowledge.add_question(
                    AddQuestionRequest(
                        topic=args.topic,
                        question=args.question,
                        answer=args.answer,
                        tags=_tags(args),
                        source_refs=_refs(args),
                    )
                )
                print(
                    json.dumps(
                        {"status": "added", "okf_question": str(result.path)},
                        ensure_ascii=False,
                    )
                )
                return 0
            if args.knowledge_command == "add-entity":
                result = knowledge.add_entity(
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
                print(
                    json.dumps(
                        {"status": "added", "okf_entity": str(result.path)},
                        ensure_ascii=False,
                    )
                )
                return 0
            if args.knowledge_command == "promote":
                result = knowledge.promote_source(
                    args.source, topic=args.topic, summary=args.summary
                )
                print(
                    json.dumps(
                        {"status": "promoted", "okf_concept": str(result.path)},
                        ensure_ascii=False,
                    )
                )
                return 0
            if args.knowledge_command == "refresh":
                result = LifecycleModule(workspace).refresh_topic(
                    args.topic,
                    in_place=args.in_place,
                    summary=args.summary,
                )
                print(json.dumps(result, ensure_ascii=False, default=str))
                return 0
            if args.knowledge_command == "topics":
                classifier = ClassifyModule(workspace)
                print(
                    json.dumps(
                        {
                            "topics": classifier.list_topics(),
                            "tags": classifier.list_tags(),
                            "domains": classifier.taxonomy.get("domains", {}),
                        },
                        ensure_ascii=False,
                    )
                )
                return 0
            return _argument_error(
                parser,
                "the following arguments are required: knowledge_command",
            )
        if args.command == "search":
            workspace = _workspace_from_args(args)
            home = _home_from_args(args)
            if workspace is None and home is None:
                home = AlcoveHome.init()
            search_module = SearchModule(workspace, home=home)
            if args.unindexed:
                if workspace is None:
                    return _argument_error(parser, "search --unindexed requires --workspace")
                issues = ValidateModule(workspace).validate(strict_quality=False)
                if args.json:
                    print(json.dumps({"issues": issues}, ensure_ascii=False, indent=2))
                else:
                    for issue in issues:
                        print(f"{issue['kind']} | {issue['path']} | {issue['message']}")
                return 1 if issues else 0
            if args.tags:
                results = search_module.tags()
                if args.json:
                    print(json.dumps(results, ensure_ascii=False, indent=2))
                else:
                    for row in results:
                        print(f"{row['tag']} | {row['count']}")
                return 0
            if args.tag_doctor:
                results = search_module.tag_doctor()
                if args.json:
                    print(json.dumps(results, ensure_ascii=False, indent=2))
                else:
                    for row in results:
                        print(f"{row['canonical']} | {row['count']} | {', '.join(row['variants'])}")
                return 0
            if args.recent is not None:
                results = search_module.recent(args.recent)
            else:
                results = search_module.search(
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
                    )
                )
            if args.json:
                print(json.dumps(results, ensure_ascii=False, indent=2))
            else:
                _print_search_rows(results)
            return 0
        if args.command == "pin":
            workspace = _workspace_from_args(args)
            home = _home_from_args(args)
            pins = PinsModule(workspace, home=home)
            if args.pin_command == "add":
                result = pins.add(
                    AddPinRequest(
                        title=args.title,
                        description=args.description,
                        tags=_tags(args),
                        priority=args.priority,
                        source_refs=_refs(args),
                    )
                )
                payload = {
                    "status": "pinned",
                    "path": str(result.path),
                    "pin": _pin_dict(result.pin),
                }
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    _print_path("pin", result.path)
                return 0
            if args.pin_command == "list":
                results = [_pin_dict(pin) for pin in pins.list(args.tag, args.status)]
                if args.json:
                    print(json.dumps(results, ensure_ascii=False, indent=2))
                else:
                    for pin in results:
                        print(
                            f"{pin['priority']} | {pin['status']} | {pin['title']} | {pin['path']}"
                        )
                return 0
            if args.pin_command == "archive":
                payload = pins.archive(args.pin_id, confirm=args.confirm)
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"{payload['status']}: {payload['path']}")
                return 0
            return _argument_error(parser, "the following arguments are required: pin_command")
        if args.command == "idea":
            workspace = _workspace_from_args(args)
            home = _home_from_args(args)
            tasks = TasksModule(workspace, home=home)
            if args.idea_command == "add":
                idea = tasks.idea_add(
                    AddIdeaRequest(
                        title=args.title,
                        notes=args.notes,
                        tags=_tags(args),
                    )
                )
                payload = {"status": "added", "idea": _idea_dict(idea)}
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"idea: {idea.id}")
                return 0
            if args.idea_command == "list":
                results = [_idea_dict(idea) for idea in tasks.idea_list(args.status)]
                if args.json:
                    print(json.dumps(results, ensure_ascii=False, indent=2))
                else:
                    for idea in results:
                        print(f"{idea['status']} | {idea['title']} | {idea['id']}")
                return 0
            if args.idea_command == "promote":
                task = tasks.idea_promote_to_task(
                    args.idea_id,
                    priority=args.priority,
                    due=args.due,
                    notes=args.notes,
                )
                idea = next(
                    item
                    for item in tasks.idea_list(status="promoted")
                    if item.promoted_task_id == task.id
                )
                payload = {
                    "status": "promoted",
                    "idea": _idea_dict(idea),
                    "task": _task_dict(task),
                }
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"task: {task.id}")
                return 0
            return _argument_error(parser, "the following arguments are required: idea_command")
        if args.command == "task":
            workspace = _workspace_from_args(args)
            home = _home_from_args(args)
            tasks = TasksModule(workspace, home=home)
            if args.task_command == "add":
                task = tasks.task_add(
                    AddTaskRequest(
                        title=args.title,
                        notes=args.notes,
                        tags=_tags(args),
                        priority=args.priority,
                        due=args.due,
                    )
                )
                payload = {"status": "added", "task": _task_dict(task)}
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"task: {task.id}")
                return 0
            if args.task_command == "list":
                results = [_task_dict(task) for task in tasks.task_list(args.status)]
                if args.json:
                    print(json.dumps(results, ensure_ascii=False, indent=2))
                else:
                    for task in results:
                        print(
                            f"{task['priority']} | {task['status']} | "
                            f"{task['title']} | {task['id']}"
                        )
                return 0
            if args.task_command == "complete":
                task = tasks.task_complete(args.task_id)
                payload = {"status": "completed", "task": _task_dict(task)}
                print(json.dumps(payload, ensure_ascii=False) if args.json else task.id)
                return 0
            if args.task_command == "cancel":
                task = tasks.task_cancel(args.task_id)
                payload = {"status": "cancelled", "task": _task_dict(task)}
                print(json.dumps(payload, ensure_ascii=False) if args.json else task.id)
                return 0
            if args.task_command == "routine-add":
                routine = tasks.routine_add(
                    AddRoutineRequest(
                        title=args.title,
                        notes=args.notes,
                        tags=_tags(args),
                        priority=args.priority,
                        every_days=args.every_days,
                        next_due=args.next_due,
                    )
                )
                payload = {"status": "added", "routine": _routine_dict(routine)}
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"routine: {routine.id}")
                return 0
            if args.task_command == "routine-list":
                results = [_routine_dict(routine) for routine in tasks.routine_list(args.status)]
                if args.json:
                    print(json.dumps(results, ensure_ascii=False, indent=2))
                else:
                    for routine in results:
                        print(
                            f"{routine['priority']} | {routine['status']} | "
                            f"{routine['next_due']} | {routine['title']} | {routine['id']}"
                        )
                return 0
            if args.task_command == "materialize-due":
                today = args.today or None
                created = tasks.routine_materialize_due(today=today)
                payload = {
                    "status": "materialized",
                    "created": [_task_dict(task) for task in created],
                }
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"created: {len(created)}")
                return 0
            return _argument_error(parser, "the following arguments are required: task_command")
        if args.command == "mount":
            workspace = _workspace_from_args(args)
            home = _home_from_args(args)
            mounts = MountsModule(workspace, home=home)
            if args.mount_command == "add":
                mount = mounts.add(
                    AddMountRequest(
                        path=args.path,
                        name=args.name,
                        mount_type=args.type,
                        tags=_tags(args),
                    )
                )
                payload = {"status": "mounted", "mount": asdict(mount)}
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"mount: {mount.id}")
                return 0
            if args.mount_command == "list":
                results = [asdict(mount) for mount in mounts.list(args.status)]
                if args.json:
                    print(json.dumps(results, ensure_ascii=False, indent=2))
                else:
                    for mount in results:
                        print(f"{mount['type']} | {mount['name']} | {mount['path']}")
                return 0
            if args.mount_command == "scan":
                report = mounts.scan(args.mount_id)
                if args.json:
                    print(json.dumps(report, ensure_ascii=False, indent=2))
                else:
                    print(f"scanned: {report['scanned']}, skipped: {report['skipped']}")
                return 0
            return _argument_error(parser, "the following arguments are required: mount_command")
        if args.command == "connector":
            workspace = _workspace_from_args(args)
            home = _home_from_args(args)
            if args.connector_command == "apple-notes":
                if args.apple_notes_command == "index":
                    report = AppleNotesConnector(workspace, home=home).import_export(
                        AppleNotesImportRequest(
                            export_dir=args.export_dir,
                            tags=_tags(args),
                        )
                    )
                    if args.json:
                        print(json.dumps(report, ensure_ascii=False, indent=2))
                    else:
                        print(f"indexed: {report['scanned']}, skipped: {report['skipped']}")
                    return 0
                return _argument_error(
                    parser,
                    "the following arguments are required: apple_notes_command",
                )
            if args.connector_command == "github-stars":
                if args.github_stars_command == "index":
                    report = GitHubStarsConnector(workspace, home=home).import_export(
                        GitHubStarsImportRequest(
                            export_file=args.export_file,
                            tags=_tags(args),
                        )
                    )
                    if args.json:
                        print(json.dumps(report, ensure_ascii=False, indent=2))
                    else:
                        print(f"indexed: {report['scanned']}, skipped: {report['skipped']}")
                    return 0
                return _argument_error(
                    parser,
                    "the following arguments are required: github_stars_command",
                )
            return _argument_error(
                parser,
                "the following arguments are required: connector_command",
            )
        if args.command == "link":
            workspace = _required_workspace(parser, args)
            if isinstance(workspace, int):
                return workspace
            if args.link_command == "source":
                result = LinkingModule(workspace).link_source(
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
            home = AlcoveHome.init(Path(args.home)) if args.home else AlcoveHome.init()
            if args.export_command == "global":
                result = ExportModule(home).export_global(args.output_dir)
                if args.json:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    print(f"exported: {result['output_dir']}")
                return 0
            return _argument_error(
                parser,
                "the following arguments are required: export_command",
            )
        if args.command == "serve":
            if args.mcp:
                workspace = _workspace_from_args(args)
                workspace_arg = str(workspace.root) if workspace is not None else "."
                run_mcp_server(workspace_arg, args.home or None)
                return 0
            return _argument_error(parser, "serve requires --mcp")
        if args.command == "validate":
            workspace = _required_workspace(parser, args)
            if isinstance(workspace, int):
                return workspace
            issues = ValidateModule(workspace).validate(strict_quality=args.strict_quality)
            if args.json:
                print(json.dumps({"issues": issues}, ensure_ascii=False, indent=2))
            else:
                for issue in issues:
                    print(f"{issue['kind']} | {issue['path']} | {issue['message']}")
            return 1 if issues else 0
        if args.command == "gardener":
            workspace = _required_workspace(parser, args)
            if isinstance(workspace, int):
                return workspace
            report = GardenerModule(workspace).gardener(prune=args.prune)
            payload = {"issues": report.issues, "actions": report.actions}
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                for issue in report.issues:
                    print(f"{issue['kind']} | {issue['path']} | {issue['message']}")
                for action in report.actions:
                    print(f"{action['action']} | {action['path']}")
            return 0
        return _argument_error(parser, "the following arguments are required: command")
    except (AlcoveError, FileNotFoundError, ValueError) as exc:
        print(f"alcove: {exc}", file=sys.stderr)
        return 2


def entrypoint() -> None:
    raise SystemExit(main())
