from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ALCOVE_SECTION_START = "<!-- ALCOVE ENTRY START -->"
ALCOVE_SECTION_END = "<!-- ALCOVE ENTRY END -->"


@dataclass(frozen=True)
class ProfileArtifact:
    path: Path
    content: str


def upsert_marked_section(existing: str, section: str) -> str:
    if ALCOVE_SECTION_START not in existing:
        prefix = existing.rstrip()
        if prefix:
            return f"{prefix}\n\n{section}"
        return section
    start = existing.index(ALCOVE_SECTION_START)
    end = existing.index(ALCOVE_SECTION_END, start) + len(ALCOVE_SECTION_END)
    prefix = existing[:start].rstrip()
    suffix = existing[end:].lstrip()
    if prefix:
        return f"{prefix}\n\n{section}{suffix}"
    return f"{section}{suffix}"


def entry_section(profile: str, home: Path, default_kb: str, home_part: str) -> str:
    kb_part = f" --kb {default_kb}" if default_kb else ""
    if profile == "managed-kb":
        return _managed_kb_entry_section(home, default_kb, home_part)
    description = (
        "This directory is the Alcove hub workspace."
        if profile == "hub"
        else "This directory is an Alcove managed knowledge base workspace."
    )
    return (
        f"{ALCOVE_SECTION_START}\n"
        "## Alcove Entry\n\n"
        f"{description}\n\n"
        f"- Home: `{home}`\n"
        f"- Default KB: `{default_kb or '(none)'}`\n\n"
        "Common commands:\n\n"
        "```sh\n"
        f'alcove search{home_part}{kb_part} "query"\n'
        f"alcove inbox{home_part}{kb_part} peek\n"
        f"alcove pin{home_part} list\n"
        f"alcove task{home_part} list\n"
        "```\n"
        f"{ALCOVE_SECTION_END}\n"
    )


def skill_content(profile: str, default_kb: str, home_part: str) -> str:
    kb_part = f" --kb {default_kb}" if default_kb else ""
    if profile == "hub":
        description = (
            "Use for Alcove hub conversations: search, pins, tasks, mounts, "
            "connectors, and managed KB routing."
        )
    else:
        description = (
            "Use inside an Alcove managed knowledge base for inbox review, "
            "OKF notes, validation, and gardening."
        )
    return (
        "# Alcove Entry\n\n"
        f"{description}\n\n"
        "## Commands\n\n"
        "```sh\n"
        f'alcove search{home_part}{kb_part} "query"\n'
        f"alcove inbox{home_part}{kb_part} peek --json\n"
        f"alcove validate{home_part}{kb_part} --json\n"
        "```\n"
    )


def managed_kb_claude_artifacts(root: Path, kb: str) -> list[ProfileArtifact]:
    return [
        ProfileArtifact(
            root / ".claude" / "commands" / "inbox-peek.md",
            _managed_kb_inbox_peek_command(kb),
        ),
        ProfileArtifact(
            root / ".claude" / "commands" / "into-kb.md",
            _managed_kb_into_kb_command(kb),
        ),
        ProfileArtifact(
            root / ".claude" / "skills" / "notes-search" / "SKILL.md",
            _managed_kb_notes_search_skill(kb),
        ),
        ProfileArtifact(
            root / ".claude" / "skills" / "social_post_manager" / "SKILL.md",
            _managed_kb_social_post_manager_skill(kb, root),
        ),
    ]


def managed_kb_codex_artifacts(root: Path, kb: str) -> list[ProfileArtifact]:
    return [
        ProfileArtifact(
            root / ".agents" / "skills" / "notes-search" / "SKILL.md",
            _managed_kb_notes_search_skill(kb),
        ),
        ProfileArtifact(
            root / ".agents" / "skills" / "social_post_manager" / "SKILL.md",
            _managed_kb_social_post_manager_skill(kb, root),
        ),
    ]


def _managed_kb_entry_section(home: Path, kb: str, home_part: str) -> str:
    kb_part = f" --kb {kb}" if kb else ""
    return f"""{ALCOVE_SECTION_START}
## Alcove Managed KB Entry

This directory is an Alcove managed knowledge base workspace. Keep this file
thin: Skills and commands hold the detailed workflows.

- Home: `{home}`
- Default KB: `{kb or "(none)"}`
- Managed data here: `knowledge/`, `inbox/`, `archive/`, `todo/`
- Global data outside this repo: pins, tasks, mounts, connectors, and KB registry

Common commands:

```sh
alcove search{home_part}{kb_part} "query"
alcove inbox{home_part}{kb_part} peek --json
alcove validate{home_part}{kb_part} --json
```

Inbox posts require explicit per-post confirmation before archive, note, todo,
or delete. A raw link means capture to inbox, not permission to process existing
inbox items.

Use project skills:

- `social_post_manager`: capture links, review inbox, archive/note/delete/todo.
- `notes-search`: search, tags, recent docs, and tag audits.
- `alcove-kb`: direct Alcove command reference.

Do not recreate project-local `post_manager.py`, `okf_manager.py`, or
`notes_search.py` scripts.
{ALCOVE_SECTION_END}
"""


def _managed_kb_inbox_peek_command(kb: str) -> str:
    return f"""---
description: Peek the oldest Alcove inbox item, summarize it structurally, and wait for an explicit action.
allowed-tools: Read, Bash
---

Show the oldest pending inbox item without changing files.

Run:

```sh
alcove inbox --kb {kb} peek --json
```

Then present:

- metadata: platform, title, date, source URL
- topic: one sentence
- core content: grouped bullets or a compact table
- key numbers / quoted short phrases
- TL;DR: 3-6 bullets

Rules:

- Do not archive, note, delete, todo, or peek the next item.
- Do not mechanically list image 1/image 2/image 3; synthesize the content.
- Wait for an explicit user action such as archive, note, todo, delete, or skip.
- If inbox is empty, say there is no pending item.
"""


def _managed_kb_into_kb_command(kb: str) -> str:
    return f"""---
description: Archive the current inbox item into Alcove knowledge as a Source, optionally with a Knowledge Concept.
allowed-tools: Read, Bash, Glob, Grep
---

Process the inbox item that was just shown by `/inbox-peek`.

Use archive mode when the user says archive, store, or keep only the source:

```sh
alcove inbox --kb {kb} archive <folder> <domain/topic> --summary "..." --json
```

Use note mode when the user says note, summarize into knowledge, concept, or
record notes:

```sh
alcove inbox --kb {kb} note <folder> <domain/topic> --summary "..." --json
```

Optional flags:

```sh
--tags "tag-a,tag-b"
--no-auto-tags
--supersede-similar
--selected-takeaways "1,2,5"
--why "why this is worth keeping"
--connection "how it connects to current work"
--action "small next action"
--personal-note "user's own view"
```

Rules:

- The user must authorize the action for the current item.
- Pick a concrete `domain/topic`; do not omit topic.
- Prefer existing taxonomy topics. Add a new lowercase kebab slug only when no
  suitable topic exists.
- Run validation after a mutating operation:

```sh
alcove validate --kb {kb} --json
```
"""


def _managed_kb_notes_search_skill(kb: str) -> str:
    return f"""---
name: notes-search
description: Use when searching, browsing, listing tags, checking recent items, or auditing tags in an Alcove managed knowledge base.
type: project
---

# Alcove Notes Search

This skill is read-only. Use Alcove CLI; do not call retired project-local
search scripts.

## Commands

```sh
alcove search --kb {kb} "query" --json
alcove search --kb {kb} --tags --json
alcove search --kb {kb} --recent 20 --json
alcove search --kb {kb} --tag <tag> --json
alcove search --kb {kb} --topic <domain/topic> --json
alcove search --kb {kb} --platform <platform> --json
alcove search --kb {kb} --type "Knowledge Concept" --json
alcove search --kb {kb} --tag-doctor --json
alcove search --kb {kb} --unindexed --json
```

Search results include type, title, domain, topic, platform, date, tags,
confidence, status, resource, and path. Use `archive/` only for provenance
tracing; `knowledge/` is the formal knowledge base.
"""


def _managed_kb_social_post_manager_skill(kb: str, root: Path) -> str:
    return f"""---
name: social_post_manager
description: Use when capturing social/web links into an Alcove inbox or reviewing, summarizing, archiving, noting, deleting, or deferring managed-KB inbox items.
type: project
---

# Social Post Manager

This skill keeps the original social-media-posts workflow while routing all
knowledge behavior through Alcove and all capture behavior through Clipsmith.

## Capture Links

If the user sends a downloadable social or web link, default to capture into
inbox. Do not process existing inbox items just because a link was captured.

Expected capture flow:

```sh
clipsmith providers --json
clipsmith capture start "<url>" --state-dir /tmp/clipsmith-state
clipsmith validate-bundle "<bundle_dir>" --json
clipsmith capture finalize "<job_id_or_job_path>" "<bundle_dir>" --state-dir /tmp/clipsmith-state
clipsmith sink alcove-inbox "<bundle_dir>" {root} --json
```

Platform expectations:

- XiaoHongShu: `xhslink.com` or `xiaohongshu.com/explore/` -> `inbox/xhs/`
- X/Twitter: `x.com/` or `twitter.com/` -> `inbox/x/`
- WeChat: `mp.weixin.qq.com` or `weixin.qq.com` -> `inbox/wechat/`
- Generic web: normal article URLs -> `inbox/web/`

OCR and bundle repair belong in Clipsmith, not in this repository.

## Review Inbox

Peek:

```sh
alcove inbox --kb {kb} peek --json
```

Read a selected item:

```sh
alcove inbox --kb {kb} read <folder> --json
```

Classify for suggestions:

```sh
alcove inbox --kb {kb} classify <folder> [domain/topic]
```

## Mutating Actions

Never mutate without explicit user authorization for the current item.

Archive as Source:

```sh
alcove inbox --kb {kb} archive <folder> <domain/topic> --summary "..." --json
```

Write Source + Knowledge Concept:

```sh
alcove inbox --kb {kb} note <folder> <domain/topic> --summary "..." --json
```

Move to todo:

```sh
alcove inbox --kb {kb} todo <folder> "reason"
```

Delete:

```sh
alcove inbox --kb {kb} delete <folder> --confirm
```

Add direct knowledge:

```sh
alcove knowledge --kb {kb} add-note <domain/topic> "Title" --summary "..."
alcove knowledge --kb {kb} add-question <domain/topic> "Question" --answer "..."
alcove knowledge --kb {kb} add-entity <domain/topic> "Name" --kind tool --summary "..."
```

## Decision Rules

- Source: raw evidence, new material, or items worth keeping but not yet digested.
- Knowledge Concept: durable concept or synthesized note.
- Question: stable answer likely to be asked again.
- Entity: tool, project, company, person, platform, or object profile.
- Todo: useful but not ready to process.

When the user wants low-friction judgment, offer numbered recommendations. If
they reply with numbers such as `1,2,5`, map those into
`--selected-takeaways` and put their own view in `--personal-note`.

## Safety

- One inbox item at a time unless the user explicitly authorizes a batch.
- Do not create `notes/`.
- Do not recreate retired project-local scripts.
- Run `alcove validate --kb {kb} --json` after mutating knowledge.
"""
