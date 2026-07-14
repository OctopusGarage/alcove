from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from alcove.application import AlcoveApplication
from alcove.prompts import AddPromptRequest


ArgumentError = Callable[[argparse.ArgumentParser, str], int]
RuntimeFactory = Callable[[Any], Any]
ListReader = Callable[[Any], list[str]]
CsvReader = Callable[[Any], list[str]]


def handle_prompt_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    runtime_from_args: RuntimeFactory,
    tags_from_args: ListReader,
    refs_from_args: ListReader,
    split_csv_values: CsvReader,
    argument_error: ArgumentError,
) -> int:
    app = AlcoveApplication(runtime_from_args(args))
    if args.prompt_command == "save":
        if not args.proposal_id and args.force and (not args.title or not args.content):
            return argument_error(
                parser,
                "prompt save with --force requires title and --content",
            )
        payload = app.global_home.prompt_save_payload(
            _prompt_request_from_args(
                args,
                tags_from_args=tags_from_args,
                refs_from_args=refs_from_args,
                split_csv_values=split_csv_values,
            )
            if not args.proposal_id
            else None,
            proposal_id=args.proposal_id,
            force=args.force,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"prompt: {payload['prompt']['id']} | {payload['path']}")
        return 0
    if args.prompt_command == "propose":
        payload = app.global_home.prompt_propose_payload(
            _prompt_request_from_args(
                args,
                tags_from_args=tags_from_args,
                refs_from_args=refs_from_args,
                split_csv_values=split_csv_values,
            ),
            ai_eval_provider=str(getattr(args, "ai_eval_provider", "") or ""),
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _print_prompt_proposal(payload)
        return 0
    if args.prompt_command == "proposal":
        payload = app.global_home.prompt_proposal_payload(args.proposal_id)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _print_prompt_proposal(payload)
        return 0
    if args.prompt_command == "search":
        payload = app.global_home.prompt_search_payload(
            query=args.query,
            tag=args.tag,
            status=args.status,
            kind=args.kind,
            domain=args.domain,
            surface=args.surface,
        )
        if args.json:
            print(json.dumps(payload["prompts"], ensure_ascii=False, indent=2))
        else:
            for prompt in payload["prompts"]:
                print(f"{prompt['status']} | {prompt['title']} | {prompt['id']}")
        return 0
    if args.prompt_command == "recommend":
        payload = app.global_home.prompt_recommend_payload(
            scenario=args.scenario,
            limit=args.limit,
            status=args.status,
            surface=args.surface,
        )
        if args.json:
            print(json.dumps(payload["recommendations"], ensure_ascii=False, indent=2))
        else:
            _print_prompt_recommendations(payload["recommendations"])
        return 0
    if args.prompt_command == "compose":
        payload = app.global_home.prompt_compose_payload(
            scenario=args.scenario,
            limit=args.limit,
            status=args.status,
            surface=args.surface,
            max_chars_per_prompt=args.max_chars_per_prompt,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(payload["prompt"], end="")
        return 0
    if args.prompt_command == "audit":
        payload = app.global_home.prompt_audit_payload(status=args.status)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(
                f"status: {payload['status']} | "
                f"prompts: {payload['counts']['prompts']} | "
                f"issues: {payload['counts']['issues']}"
            )
            for issue in payload["issues"]:
                if issue["severity"] == "info":
                    continue
                print(
                    f"{issue['severity']} | {issue['kind']} | {issue['title']} | {issue['message']}"
                )
        return 0
    if args.prompt_command == "candidates":
        return _handle_prompt_candidates(args, app)
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
    return argument_error(parser, "the following arguments are required: prompt_command")


def _handle_prompt_candidates(args: Any, app: AlcoveApplication) -> int:
    if args.prompt_candidates_command == "scan":
        payload = app.global_home.prompt_candidates_scan_payload(
            [Path(path) for path in args.paths]
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"candidates: {payload['count']} | {payload['index_path']}")
        return 0
    if args.prompt_candidates_command == "list":
        payload = app.global_home.prompt_candidates_list_payload(
            min_score=args.min_score,
        )
        if args.json:
            print(json.dumps(payload["candidates"], ensure_ascii=False, indent=2))
        else:
            for candidate in payload["candidates"]:
                print(f"{candidate['score']:.2f} | {candidate['kind']} | {candidate['title']}")
        return 0
    if args.prompt_candidates_command == "promote":
        payload = app.global_home.prompt_candidates_promote_payload(
            min_score=args.min_score,
            limit=args.limit,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"promoted: {payload['count']} | {payload['index_path']}")
        return 0
    return 0


def _prompt_request_from_args(
    args: Any,
    *,
    tags_from_args: ListReader,
    refs_from_args: ListReader,
    split_csv_values: CsvReader,
) -> AddPromptRequest:
    return AddPromptRequest(
        title=str(getattr(args, "title", "") or ""),
        content=str(getattr(args, "content", "") or ""),
        description=str(getattr(args, "description", "") or ""),
        tags=tags_from_args(args),
        use_cases=getattr(args, "use_case", []) + split_csv_values(getattr(args, "use_cases", [])),
        source_refs=refs_from_args(args),
        kind=str(getattr(args, "kind", "") or "full_prompt"),
        domain=str(getattr(args, "domain", "") or ""),
        intent=str(getattr(args, "intent", "") or ""),
        surfaces=getattr(args, "surface", []) + split_csv_values(getattr(args, "surfaces", [])),
        triggers=getattr(args, "trigger", []) + split_csv_values(getattr(args, "triggers", [])),
        inputs=getattr(args, "input", []) + split_csv_values(getattr(args, "inputs", [])),
        outputs=getattr(args, "output", []) + split_csv_values(getattr(args, "outputs", [])),
        quality=_quality_from_args(args),
    )


def _quality_from_args(args: Any) -> dict[str, Any]:
    quality: dict[str, Any] = {}
    status = str(getattr(args, "quality_status", "") or "")
    notes = str(getattr(args, "quality_notes", "") or "")
    score = getattr(args, "quality_score", None)
    if status:
        quality["status"] = status
    if score is not None:
        quality["score"] = score
    if notes:
        quality["notes"] = notes
    return quality


def _print_prompt_recommendations(recommendations: list[dict[str, Any]]) -> None:
    if not recommendations:
        print("No matching reusable prompts found.")
        return
    print(f"Recommended prompts ({min(len(recommendations), 5)}):")
    for index, item in enumerate(recommendations[:5], start=1):
        prompt = item["prompt"]
        print(f"{index}. {prompt['title']} ({prompt['id']})")
        print(f"   score: {item['score']:.2f} | {prompt['kind']} | {prompt['domain'] or '-'}")
        if prompt.get("description"):
            print(f"   use: {prompt['description']}")
        if item.get("reasons"):
            print(f"   why: {'; '.join(item['reasons'][:2])}")
        if prompt.get("use_cases"):
            print(f"   cases: {', '.join(prompt['use_cases'][:3])}")


def _print_prompt_proposal(payload: dict[str, Any]) -> None:
    print(f"proposal: {payload['id']} | action: {payload['action']}")
    print(f"title: {payload['request']['title']}")
    print(
        f"kind/domain/intent: {payload['request']['kind']} / "
        f"{payload['request']['domain']} / {payload['request']['intent']}"
    )
    if payload.get("warnings"):
        print("warnings: " + ", ".join(payload["warnings"]))
    if payload.get("similar"):
        print("similar prompts:")
        _print_prompt_recommendations(payload["similar"][:5])
    if payload.get("next_steps"):
        print("next steps:")
        for step in payload["next_steps"]:
            print(f"- {step}")
