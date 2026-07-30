from __future__ import annotations

import re
from pathlib import Path

_PROFILE_SKILL_TEMPLATES = {
    "hub": "hub/skills/alcove-hub/SKILL.md",
    "managed-kb": "managed-kb/skills/alcove-kb/SKILL.md",
    "workspace": "workspace/skills/alcove-workspace/SKILL.md",
}

_FENCED_COMMAND_ROOTS = {
    "hub": (
        "blog",
        "connector",
        "export",
        "inbox",
        "kb",
        "mount",
        "pin",
        "project",
        "prompt",
        "radar",
        "search",
        "task",
        "workspace",
    ),
    "managed-kb": ("inbox", "knowledge", "search", "validate"),
    "workspace": ("idea", "pin", "prompt", "search", "task", "workspace"),
}

_INLINE_HOME_PART_LINES = {
    "hub": frozenset(
        {
            '| Broad personal knowledge question | `alcove search "query" --json`, then inspect returned OKF/source/mount/connector refs | none |',
            "| Current managed KB inbox review | `alcove inbox --kb <kb-name> peek --json`; read full item before summarizing if truncated | archive/note/todo/delete only after explicit confirmation |",
            "| Save copied article or discussion note | search first for duplicates and choose target KB | `alcove inbox --kb <kb-name> manual-add ...` or `alcove knowledge ...` |",
            '| Save stable reference, preference, command, shortcut | `alcove pin search "query" --json` | `alcove pin add/update ...` |',
            '| Save reusable prompt | `alcove prompt recommend "scenario" --json` and `alcove prompt propose ... --json` | `alcove prompt save --proposal-id <id>` after proposal review |',
            "| Check monitored blogs now | `alcove blog list --status '' --json`, then `alcove blog check --json` or `alcove blog check <source-id> --json` | only add/update sources after explicit confirmation |",
            "| Run an information radar | `alcove radar list --json`, then `alcove radar status <radar-id> --json` | `alcove radar run <radar-id> --json`, `--force --ai --notify`, or `--skip-fetch --force --ai --notify` after choosing an existing definition |",
            "  `alcove blog list --status '' --json`, inspect `last_error`, then run",
            "  `alcove blog check <source-id> --json` to retry that source immediately.",
            "  captured `post.md` / `summary.md`, or run `alcove blog check --summary --json`",
            "- Use `alcove radar status <radar-id> --json` to inspect latest reports and source health before rerunning.",
            "- Use `alcove radar run <radar-id> --json` for a normal active refresh.",
            "- Use `alcove radar run <radar-id> --force --ai --notify --json` when the user asks to rerun, refresh now, summarize with AI, and send configured notifications.",
            "- Use `alcove radar run <radar-id> --skip-fetch --force --ai --notify --json` when the user asks to analyze or resend already fetched results without touching external sources.",
            '  `alcove prompt recommend "<scenario>" --json` and present at most five',
            '  candidates, use `alcove prompt compose "<scenario>" --json` or inspect the',
            "  chosen prompts with `alcove prompt get`.",
            '  `alcove prompt recommend "<scenario>" --json`. If a similar prompt exists,',
            '  `alcove prompt propose "<title>" --content "..." --json`. Use',
            "- Only accept a proposal with `alcove prompt save --proposal-id <id> --json`",
            "- Use direct `alcove prompt save --force ...` only for explicit repair or",
        }
    ),
    "managed-kb": frozenset(
        {
            '| Broad personal knowledge question | `alcove search "query" --json`, then inspect returned OKF/source/mount/connector refs | none |',
            '| Current KB question | `alcove search "query" --json` from this workspace | none |',
            "| Inbox review | `alcove inbox peek --json`; read full item before summarizing if truncated | archive/note/todo/delete only after explicit confirmation |",
            "| Save copied article or discussion note | search first for duplicates | `alcove inbox manual-add ...` or `alcove knowledge ...` |",
            "| Revise existing OKF note | inspect the target OKF path first | `alcove knowledge revise ...`, then `alcove validate --json` |",
        }
    ),
    "workspace": frozenset(),
}

_CODE_SPAN_PATTERN = re.compile(r"`(alcove [^`]+)`")


def profile_skill_content(profile: str, home_part: str) -> str | None:
    source_path = profile_skill_source_path(profile)
    if source_path is None:
        return None
    content = source_path.read_text(encoding="utf-8")
    if not home_part:
        return content
    return _apply_home_part(
        content,
        home_part,
        command_roots=_FENCED_COMMAND_ROOTS[profile],
        inline_home_part_lines=_INLINE_HOME_PART_LINES[profile],
    )


def profile_skill_source_path(profile: str) -> Path | None:
    relative = _PROFILE_SKILL_TEMPLATES.get(profile)
    if relative is None:
        return None
    return profile_template_path(relative)


def profile_template_path(relative: str) -> Path:
    return Path(__file__).resolve().parent / "profile_templates" / relative


def _apply_home_part(
    content: str,
    home_part: str,
    *,
    command_roots: tuple[str, ...],
    inline_home_part_lines: frozenset[str],
) -> str:
    rendered_lines: list[str] = []
    in_fence = False
    for line in content.splitlines(keepends=True):
        body = line.removesuffix("\n")
        if body.startswith("```"):
            in_fence = not in_fence
            rendered_lines.append(line)
            continue
        if in_fence:
            rendered_lines.append(_insert_home_part_in_command_line(line, home_part, command_roots))
            continue
        if body in inline_home_part_lines:
            rendered_lines.append(_insert_home_part_in_code_spans(line, home_part, command_roots))
            continue
        rendered_lines.append(line)
    return "".join(rendered_lines)


def _insert_home_part_in_code_spans(
    line: str, home_part: str, command_roots: tuple[str, ...]
) -> str:
    def replace(match: re.Match[str]) -> str:
        if match.group(1) == "alcove knowledge ...":
            return match.group(0)
        command = _insert_home_part_in_command(match.group(1), home_part, command_roots)
        return f"`{command}`"

    return _CODE_SPAN_PATTERN.sub(replace, line)


def _insert_home_part_in_command_line(
    line: str, home_part: str, command_roots: tuple[str, ...]
) -> str:
    newline = "\n" if line.endswith("\n") else ""
    body = line.removesuffix("\n")
    leading_width = len(body) - len(body.lstrip())
    leading = body[:leading_width]
    command = body[leading_width:]
    return f"{leading}{_insert_home_part_in_command(command, home_part, command_roots)}{newline}"


def _insert_home_part_in_command(
    command: str, home_part: str, command_roots: tuple[str, ...]
) -> str:
    for root in command_roots:
        prefix = f"alcove {root}"
        if command == prefix or command.startswith(f"{prefix} "):
            return f"{prefix}{home_part}{command[len(prefix) :]}"
    return command
