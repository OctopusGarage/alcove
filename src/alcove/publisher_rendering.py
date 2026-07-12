from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from alcove.paths import compact_user_path
from alcove.pins import Pin
from alcove.projects import ProjectRecord
from alcove.prompts import Prompt
from alcove.tasks import Idea, Routine, Task


APPLE_NOTES_RENDER_FORMAT_VERSION = "apple-notes-readable-v6"
PIN_OUTLINE_LINE_LIMIT = 28
PIN_OUTLINE_SECTION_LIMIT = 12


def render_pins_digest(*, title: str, pins: list[Pin], timestamp: str) -> str:
    generated = _singapore_time(timestamp)
    lines = [
        f"# {_title_with_icon(title)}",
        "",
        f"Updated {generated} · {len(pins)} active pins",
        "",
        "---",
        "",
    ]
    for priority in ["high", "medium", "low"]:
        group = [pin for pin in pins if pin.priority == priority]
        if not group:
            continue
        lines.extend([f"## {_priority_label(priority)} Priority ({len(group)})", ""])
        for index, pin in enumerate(group, start=1):
            lines.append(f"{index:02d}. {pin.title}")
            summary = pin.summary or pin.description
            if summary:
                lines.append(f"   {summary}")
            content = pin.content.strip()
            if content and content != summary:
                lines.append("   Notes")
                lines.extend(_pin_content_lines(content))
            if pin.tags:
                lines.append(f"   Tags  {', '.join(pin.tags)}")
            if pin.resources:
                lines.append("   Links")
                for resource in pin.resources:
                    lines.append(f"   - {resource}")
            lines.append("")
        lines.extend(["---", ""])
    if not pins:
        lines.append("No active pins.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_planner_digest(
    *,
    title: str,
    tasks: list[Task],
    ideas: list[Idea],
    routines: list[Routine],
    timestamp: str,
) -> str:
    generated = _singapore_time(timestamp)
    lines = [
        f"# {_title_with_icon(title)}",
        "",
        f"Updated {generated} · {len(tasks)} tasks · {len(ideas)} ideas · {len(routines)} routines",
        "",
        "---",
        "",
    ]
    lines.extend(_render_task_section("Pending Tasks", [_task_digest_line(task) for task in tasks]))
    lines.extend(_render_task_section("Ideas", [_idea_digest_line(idea) for idea in ideas]))
    lines.extend(
        _render_task_section(
            "Active Routines",
            [_routine_digest_line(routine) for routine in routines],
        )
    )
    return "\n".join(lines).rstrip() + "\n"


def render_prompt_library(*, title: str, prompts: list[Prompt], timestamp: str) -> str:
    generated = _singapore_time(timestamp)
    lines = [
        f"# {_title_with_icon(title)}",
        "",
        f"Updated {generated} · {len(prompts)} active prompts",
        "",
        "---",
        "",
    ]
    if not prompts:
        lines.extend(["No active prompts.", ""])
        return "\n".join(lines).rstrip() + "\n"
    by_tag = sorted(prompts, key=lambda prompt: (prompt.tags[:1] or ["zz"])[0])
    lines.extend(["## Active Prompts", ""])
    for index, prompt in enumerate(by_tag, start=1):
        lines.append(f"{index:02d}. {prompt.title}")
        if prompt.description:
            lines.append(f"   {prompt.description}")
        if prompt.use_cases:
            lines.append(f"   Use cases  {', '.join(prompt.use_cases)}")
        if prompt.tags:
            lines.append(f"   Tags  {', '.join(prompt.tags)}")
        lines.append("")
    lines.extend(["---", ""])
    return "\n".join(lines).rstrip() + "\n"


def render_project_registry(*, title: str, projects: list[ProjectRecord], timestamp: str) -> str:
    generated = _singapore_time(timestamp)
    lines = [
        f"# {_title_with_icon(title)}",
        "",
        f"Updated {generated} · {len(projects)} registered projects",
        "",
        "---",
        "",
    ]
    if not projects:
        lines.extend(["No registered projects.", ""])
        return "\n".join(lines).rstrip() + "\n"
    lines.extend(["## Projects", ""])
    for index, project in enumerate(projects, start=1):
        lines.append(f"{index:02d}. {project.alias}")
        lines.append(f"   Path  {_project_path_label(project.path)}")
        lines.append(f"   Exists  {'yes' if project.exists else 'no'}")
        if project.note:
            lines.append(f"   Note  {project.note}")
        lines.append("")
    lines.extend(["---", ""])
    return "\n".join(lines).rstrip() + "\n"


def markdown_as_apple_notes_html(markdown: str) -> str:
    html: list[str] = []
    previous_blank = False
    for raw in markdown.splitlines():
        stripped = raw.strip()
        if not stripped:
            if html and not previous_blank:
                html.append("<div><br></div>")
            previous_blank = True
            continue
        previous_blank = False
        if stripped.startswith("# "):
            html.append(
                '<div style="margin: 0 0 10px 0">'
                f'<b><span style="font-size: 24px">{escape(stripped[2:].strip())}</span></b>'
                "</div>"
            )
            continue
        if stripped.startswith("## "):
            html.append(
                '<div style="margin: 16px 0 8px 0">'
                f'<b><span style="font-size: 18px">{escape(stripped[3:].strip())}</span></b>'
                "</div>"
            )
            continue
        if stripped == "---":
            html.append(
                '<div style="margin: 12px 0; color: #8c8c8c; letter-spacing: 0">────────────</div>'
            )
            continue
        if _is_numbered_item(stripped):
            html.append(f'<div style="margin: 8px 0 4px 0"><b>{escape(stripped)}</b></div>')
            continue
        if raw.startswith("   - "):
            html.append(
                f'<div style="margin-left: 28px">• {_inline_html(stripped[2:].strip())}</div>'
            )
            continue
        if stripped.startswith("- "):
            html.append(
                f'<div style="margin-left: 18px">• {_inline_html(stripped[2:].strip())}</div>'
            )
            continue
        if raw.startswith("   "):
            html.append(f'<div style="margin-left: 22px">{_inline_html(stripped)}</div>')
            continue
        html.append(f"<div>{_inline_html(stripped)}</div>")
    return "\n".join(html).strip() or "<div><br></div>"


def content_hash(body: str) -> str:
    stable = "\n".join(
        line
        for line in body.splitlines()
        if not line.startswith("Updated: ") and not line.startswith("Updated ")
    ).strip()
    versioned = f"{APPLE_NOTES_RENDER_FORMAT_VERSION}\n{stable}"
    return f"sha256:{sha256(versioned.encode('utf-8')).hexdigest()}"


def _pin_content_lines(content: str) -> list[str]:
    source_lines = _pin_source_lines(content)
    sections = _pin_sections(source_lines)
    return _pin_full_content_lines(source_lines, sections)


def _pin_source_lines(content: str) -> list[str]:
    return [line.strip() for line in content.splitlines() if line.strip()]


def _pin_sections(source_lines: list[str]) -> list[dict[str, list[str] | str]]:
    sections: list[dict[str, list[str] | str]] = []
    current_title = "Overview"
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_lines
        if current_lines:
            sections.append({"title": current_title, "lines": current_lines})
            current_lines = []

    for line in source_lines:
        if line in {"---", "===", "—"}:
            continue
        if line.startswith("#"):
            flush()
            heading = line.lstrip("#").strip()
            current_title = heading or "Untitled"
            continue
        current_lines.append(line)
    flush()
    return sections


def _should_include_pin_outline(
    source_lines: list[str], sections: list[dict[str, list[str] | str]]
) -> bool:
    return len(source_lines) > PIN_OUTLINE_LINE_LIMIT or len(sections) > PIN_OUTLINE_SECTION_LIMIT


def _pin_full_content_lines(
    source_lines: list[str], sections: list[dict[str, list[str] | str]]
) -> list[str]:
    section_titles = [str(section["title"]) for section in sections]
    lines: list[str] = []
    if _should_include_pin_outline(source_lines, sections):
        lines.append(f"   Outline  {len(section_titles)} sections · {len(source_lines)} lines")
        for title in section_titles[:PIN_OUTLINE_SECTION_LIMIT]:
            lines.append(f"   - {title}")
        if len(section_titles) > PIN_OUTLINE_SECTION_LIMIT:
            lines.append(
                f"   - ... {len(section_titles) - PIN_OUTLINE_SECTION_LIMIT} more sections"
            )
        lines.append("")
        lines.append("   Full notes")
        lines.append("")
    for source_line in source_lines:
        if source_line in {"---", "===", "—"}:
            if lines and lines[-1] != "":
                lines.append("")
            lines.append("   ──────────")
            lines.append("")
            continue
        if source_line.startswith("#"):
            heading = source_line.lstrip("#").strip()
            if heading:
                if lines and lines[-1] != "":
                    lines.append("")
                lines.append(f"   ◼ {heading}")
                lines.append("")
            continue
        formatted = _format_pin_content_line(source_line)
        if formatted:
            lines.append(
                f"   - {formatted}"
                if _pin_line_should_be_bulleted(source_line)
                else f"   {formatted}"
            )
    return lines


def _format_pin_content_line(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""
    if stripped in {"---", "===", "—"}:
        return "──────────"
    if stripped.startswith(("- ", "* ")):
        return stripped[2:].strip()
    if stripped.startswith(">"):
        quote = stripped.lstrip(">").strip()
        return f"“{quote}”" if quote else ""
    if _is_markdown_table_row(stripped):
        cells = _markdown_table_cells(stripped)
        if not cells or _is_markdown_table_divider(cells):
            return ""
        return " | ".join(cells)
    return stripped


def _pin_line_should_be_bulleted(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith(("- ", "* ", "http://", "https://")) or _is_markdown_table_row(
        stripped
    )


def _is_markdown_table_row(line: str) -> bool:
    return line.startswith("|") and line.endswith("|") and "|" in line.strip("|")


def _markdown_table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|") if cell.strip()]


def _is_markdown_table_divider(cells: list[str]) -> bool:
    return all(set(cell.replace(":", "").replace(" ", "")) <= {"-"} for cell in cells)


def _render_task_section(title: str, rows: list[list[str]]) -> list[str]:
    section_title = _planner_section_label(title)
    if not rows:
        empty = {
            "Pending Tasks": "No pending tasks.",
            "Ideas": "No active ideas.",
            "Active Routines": "No active routines.",
        }.get(title, f"No {title.casefold()}.")
        return [f"## {section_title}", "", empty, "", "---", ""]
    lines = [f"## {section_title} ({len(rows)})", ""]
    for index, row in enumerate(rows, start=1):
        lines.append(f"{index:02d}. {row[0]}")
        for detail in row[1:]:
            lines.append(f"   {detail}")
        lines.append("")
    lines.extend(["---", ""])
    return lines


def _task_digest_line(task: Task) -> list[str]:
    details = [f"Priority  {task.priority}"]
    if task.due:
        details.append(f"Due  {task.due}")
    if task.notes:
        details.append(f"Note  {task.notes}")
    if task.tags:
        details.append(f"Tags  {', '.join(task.tags)}")
    return [task.title, *details]


def _idea_digest_line(idea: Idea) -> list[str]:
    details = []
    if idea.notes:
        details.append(f"Note  {idea.notes}")
    if idea.tags:
        details.append(f"Tags  {', '.join(idea.tags)}")
    return [idea.title, *details]


def _routine_digest_line(routine: Routine) -> list[str]:
    details = [f"Every  {routine.every_days} day{'s' if routine.every_days != 1 else ''}"]
    if routine.next_due:
        details.append(f"Next due  {routine.next_due}")
    if routine.priority:
        details.append(f"Priority  {routine.priority}")
    if routine.notes:
        details.append(f"Note  {routine.notes}")
    if routine.tags:
        details.append(f"Tags  {', '.join(routine.tags)}")
    return [routine.title, *details]


def _project_path_label(path: Path) -> str:
    label = compact_user_path(path)
    if label.startswith("/"):
        return f".../{path.name}"
    return label


def _title_with_icon(title: str) -> str:
    icons = {
        "Regular Pins": "📌",
        "TODO Pins": "✅",
        "Planner Digest": "🧭",
        "Prompt Library": "🧰",
        "Project Registry": "🗂",
    }
    icon = icons.get(title, "◇")
    return f"{icon} {title}"


def _priority_label(priority: str) -> str:
    labels = {
        "high": "High",
        "medium": "Medium",
        "low": "Low",
    }
    return labels.get(priority, priority.title())


def _planner_section_label(title: str) -> str:
    return title


def _singapore_time(timestamp: str) -> str:
    try:
        value = datetime.fromisoformat(timestamp)
    except ValueError:
        value = datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(ZoneInfo("Asia/Singapore")).strftime("%Y-%m-%d %H:%M SGT")


def _is_numbered_item(value: str) -> bool:
    number, dot, rest = value.partition(".")
    return bool(dot and rest.strip() and number.isdecimal())


def _inline_html(value: str) -> str:
    escaped = escape(value)
    if ":" not in escaped:
        return escaped
    label, rest = escaped.split(":", 1)
    if rest.startswith("//"):
        return escaped
    if 1 <= len(label) <= 18 and all(char.isalnum() or char in " /-" for char in label):
        return f"<b>{label}:</b>{rest}"
    return escaped
