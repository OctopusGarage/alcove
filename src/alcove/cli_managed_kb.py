from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from alcove.application import AlcoveApplication
from alcove.inbox_models import InboxNoteRequest
from alcove.knowledge import (
    AddConceptRequest,
    AddEntityRequest,
    AddQuestionRequest,
    NoteSourceRequest,
    ReviseKnowledgeRequest,
)


ArgumentError = Callable[[argparse.ArgumentParser, str], int]
RuntimeFactory = Callable[[Any], Any]
ListReader = Callable[[Any], list[str]]
InboxPrinter = Callable[[Any], None]
PathPrinter = Callable[[str, Path | None], None]
TakeawayReader = Callable[[str], list[str]]


def handle_inbox_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    runtime_from_args: RuntimeFactory,
    tags_from_args: ListReader,
    takeaway_reader: TakeawayReader,
    print_inbox_post: InboxPrinter,
    print_path: PathPrinter,
    argument_error: ArgumentError,
) -> int:
    app = AlcoveApplication(runtime_from_args(args))
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
                print_inbox_post(post)
        return 0
    if args.inbox_command == "read":
        post = app.inbox.inbox_read_payload(args.name)["item"]
        if args.json:
            print(json.dumps(post, ensure_ascii=False, default=str))
        else:
            print_inbox_post(post)
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
            tags=tags_from_args(args) or None,
            no_auto_tags=args.no_auto_tags,
            supersede_similar=args.supersede_similar,
            validate=args.validate,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, default=str))
        else:
            print_path("archive", Path(payload["archive"]))
            print_path("source", Path(payload["source"]))
            print(f"tags: {','.join(payload['tags'])}")
        return 0
    if args.inbox_command == "note":
        payload = app.inbox.inbox_note_payload(
            InboxNoteRequest(
                name=args.name,
                topic=args.topic,
                summary=args.summary,
                tags=tags_from_args(args),
                selected_takeaways=takeaway_reader(args.selected_takeaways),
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
            print_path("archive", Path(payload["archive"]))
            print_path("source", Path(payload["source"]))
            print_path("concept", Path(payload["concept"]) if payload["concept"] else None)
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
        print(json.dumps(app.inbox.inbox_todo_payload(args.name, args.reason), ensure_ascii=False))
        return 0
    if args.inbox_command == "delete":
        print(
            json.dumps(
                app.inbox.inbox_delete_payload(args.name, confirm=args.confirm),
                ensure_ascii=False,
            )
        )
        return 0
    return argument_error(parser, "the following arguments are required: inbox_command")


def handle_knowledge_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    runtime_from_args: RuntimeFactory,
    tags_from_args: ListReader,
    refs_from_args: ListReader,
    print_path: PathPrinter,
    argument_error: ArgumentError,
) -> int:
    app = AlcoveApplication(runtime_from_args(args))
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
        print_path("source", Path(payload["source_path"]))
        print_path("concept", Path(payload["concept_path"]) if payload["concept_path"] else None)
        return 0
    if args.knowledge_command == "add-note":
        payload = app.knowledge.knowledge_add_concept_payload(
            AddConceptRequest(
                topic=args.topic,
                title=args.title,
                summary=args.summary,
                tags=tags_from_args(args),
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
                tags=tags_from_args(args),
                source_refs=refs_from_args(args),
                reason=args.reason,
                status=args.status,
            )
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print_path("revised", Path(payload["path"]))
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
            print(f"delete preview: {payload['type']} | {payload['title']} | {payload['path']}")
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
                tags=tags_from_args(args),
                source_refs=refs_from_args(args),
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
                tags=tags_from_args(args),
                source_refs=refs_from_args(args),
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
    return argument_error(parser, "the following arguments are required: knowledge_command")
