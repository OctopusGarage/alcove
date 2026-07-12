from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ALCOVE_SECTION_START = "<!-- ALCOVE ENTRY START -->"
ALCOVE_SECTION_END = "<!-- ALCOVE ENTRY END -->"


@dataclass(frozen=True)
class ProfileArtifact:
    path: Path
    content: str
    source_path: Path | None = None


@dataclass(frozen=True)
class ProfileInstallationPack:
    profile: str
    skill_name: str

    def entry_section(self, home: str, default_kb: str, home_part: str) -> str:
        return entry_section(self.profile, home, default_kb, home_part)

    def skill_content(self, default_kb: str, home_part: str) -> str:
        return skill_content(self.profile, default_kb, home_part)

    def skill_source_path(self) -> Path | None:
        return skill_source_path(self.profile)

    def claude_artifacts(self, root: Path, default_kb: str) -> list[ProfileArtifact]:
        if self.profile != "managed-kb":
            return []
        return managed_kb_claude_artifacts(root, default_kb)

    def codex_artifacts(self, root: Path, default_kb: str) -> list[ProfileArtifact]:
        if self.profile != "managed-kb":
            return []
        return managed_kb_codex_artifacts(root, default_kb)


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


def entry_section(profile: str, home: str, default_kb: str, home_part: str) -> str:
    kb_part = f" --kb {default_kb}" if default_kb else ""
    if profile == "managed-kb":
        return _managed_kb_entry_section(home, default_kb, home_part)
    if profile == "hub":
        return _hub_entry_section(home, default_kb, home_part)
    description = (
        "This directory is the Alcove hub workspace."
        if profile == "hub"
        else "This directory is an Alcove managed knowledge base workspace."
    )
    return (
        f"{ALCOVE_SECTION_START}\n"
        "## Alcove Entry\n\n"
        f"{description}\n\n"
        "- Home: configured Alcove Home\n"
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
        return _hub_skill(default_kb, home_part)
    if profile == "managed-kb":
        return _managed_kb_skill(default_kb, home_part)
    description = "Use inside an Alcove managed knowledge base for inbox review."
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


def _hub_entry_section(home: str, default_kb: str, home_part: str) -> str:
    return f"""{ALCOVE_SECTION_START}
## Alcove Hub Entry

This directory is the main Alcove hub workspace. Use the `alcove-hub` skill for
intent routing before writing data.
If that skill is unavailable, use the commands below and ask before mutating
ambiguous data.

- Home: configured Alcove Home
- Managed KBs: discover with `alcove kb{home_part} list --json`
- Global data: pins, prompts, projects, tasks, mounts, connectors
- Managed KB data: routed through `--kb <name>`

    Operating model: read broadly, write narrowly. Search returns candidate records;
    inspect OKF paths, source refs, mount refs, connector fetches, or local files
    before answering broad or nuanced questions. This is AI-led OKF/local-file investigation.
    Use Alcove CLI/MCP for durable writes.

    After saving data, return a compact receipt with title and storage path separated:
    `标题：<stored title>` and `位置：<relative OKF path or absolute local path>`.
    Never present a full file path as the title, and do not hide the path behind a
    Markdown link whose label is the title. If a link is useful, label it explicitly
    such as `打开文件`. Include classification/tags and validation status when available.
    For OKF knowledge records, `source_refs` are internal references; put external
    URLs in the note body or a supported `resource` field instead.

Fallback routing table when project skills are unavailable:

| Intent | Read path | Governed write path |
| --- | --- | --- |
| Broad personal knowledge question | `alcove search{home_part} "query" --json`, then inspect returned OKF/source/mount/connector refs | none |
| Current managed KB inbox review | `alcove inbox{home_part} --kb <kb-name> peek --json`; read full item before summarizing if truncated | archive/note/todo/delete only after explicit confirmation |
| Save copied article or discussion note | search first for duplicates and choose target KB | `alcove inbox{home_part} --kb <kb-name> manual-add ...` or `alcove knowledge ...` |
| Save stable reference, preference, command, shortcut | `alcove pin{home_part} search "query" --json` | `alcove pin{home_part} add/update ...` |
| Save reusable prompt | `alcove prompt{home_part} search "query" --json` | `alcove prompt{home_part} save ...` |
| Track todo, idea, routine, project, mount, connector | list/search the matching module first | use the matching `alcove task/idea/routine/project/mount/connector` command |
| Check monitored blogs now | `alcove blog{home_part} list --status '' --json`, then `alcove blog{home_part} check --json` or `alcove blog{home_part} check <source-id> --json` | only add/update sources after explicit confirmation |
| Run an information radar | `alcove radar{home_part} list --json`, then `alcove radar{home_part} status <radar-id> --json` | `alcove radar{home_part} run <radar-id> --json`, `--force --ai --notify`, or `--skip-fetch --force --ai --notify` after choosing an existing definition |

Fallback blog monitor rules:

- Use `alcove blog{home_part} check --json`, not `alcove service tick`, when the
  user asks to actively check blogs now.
- For a failure alert, run `alcove blog{home_part} list --status '' --json`,
  inspect `last_error`, then retry with `alcove blog{home_part} check <source-id> --json`.
- Scheduled checks are deterministic. Do not imply Codex or Claude runs in the
  background; if the user wants interpretation, summarize from captured
  `post.md` / `summary.md` or run the check with summary enabled.

Fallback radar rules:

- Use `alcove radar{home_part} list --json` first. Radar IDs are user data and
  must not be assumed.
- Use `alcove radar{home_part} status <radar-id> --json` to inspect latest
  reports and source health before rerunning.
- Use `alcove radar{home_part} run <radar-id> --json` for a normal active refresh.
- Use `alcove radar{home_part} run <radar-id> --force --ai --notify --json`
  when the user asks to rerun, refresh now, summarize with AI, and send a
  configured notification.
- Use `alcove radar{home_part} run <radar-id> --skip-fetch --force --ai --notify --json`
  when the user asks to analyze or resend already fetched results without
  touching external sources.
- Radar runs fetch and score deterministically first. Optional `ai_summary` is
  post-report analysis only; it does not rewrite fetched items or scores.
- Scheduled radar runs start Codex or Claude only when the radar definition
  explicitly enables `ai_summary`. If AI fails, Alcove should still notify with
  the deterministic report when notification is enabled.

Common commands:

```sh
alcove kb{home_part} list --json
alcove search{home_part} "query" --json
alcove search{home_part} --kb <kb-name> "query" --json
alcove pin{home_part} list --json
alcove pin{home_part} search "" --kind regular --json
alcove prompt{home_part} search "" --json
alcove project{home_part} list --json
alcove task{home_part} list --json
alcove blog{home_part} list --status '' --json
alcove blog{home_part} check --json
alcove blog{home_part} check <source-id> --json
alcove radar{home_part} list --json
alcove radar{home_part} status <radar-id> --json
alcove radar{home_part} run <radar-id> --json
alcove radar{home_part} run <radar-id> --force --ai --notify --json
alcove radar{home_part} run <radar-id> --skip-fetch --force --ai --notify --json
```
{ALCOVE_SECTION_END}
"""


def _hub_skill(default_kb: str, home_part: str) -> str:
    _ = default_kb
    return (
        "---\n"
        "name: alcove-hub\n"
        "description: Use when working from the Alcove hub workspace or routing personal knowledge, pins, projects, prompts, tasks, mounts, connectors, or managed KB operations.\n"
        "type: project\n"
        "---\n\n"
        "# Alcove Hub\n\n"
        "This is the high-level router for Alcove. Decide the storage target before writing.\n\n"
        "## Intent Routing\n\n"
        "- knowledge article, copied source, discussion note, archive: managed KB inbox/knowledge.\n"
        "- ambiguous record, remember, save this: ask one clarifying question unless the target is obvious.\n"
        "- tiny durable reference, command, preference, shortcut: `pin --kind regular`.\n"
        "- collection wording such as 收藏, 常用收藏, or 置顶收藏: search existing pins first; if a matching collection pin such as 常用收藏 exists, update that existing collection pin instead of only creating a separate pin.\n"
        "- when saving a link with user-provided purpose, use case, or why-it-matters context, preserve that context in the target pin; do not save only the bare URL.\n"
        "- future practice or deeper-study item that should stay visible: `pin --kind todo`.\n"
        "- reusable instruction or agent prompt: `prompt`.\n"
        "- local repo/path shortcut: `project`.\n"
        "- todo, reminder, routine, follow-up: `task` or `idea`.\n"
        "- external folder or historical repo to search read-only: `mount`.\n"
        "- exported/protocol data source such as Apple Notes or GitHub Stars: `connector`.\n"
        "- blog monitoring, scheduled article checks, failure alerts, or phrases such as\n"
        "  监控博客更新 / 检查博客文章有没有更新: `blog monitor`.\n"
        "- information radar, daily briefing, 技术雷达, 新闻雷达, 股票雷达, 体育资讯: `radar`.\n\n"
        "## Fallback Routing Without Skills\n\n"
        "| Intent | Read path | Governed write path |\n"
        "| --- | --- | --- |\n"
        f'| Broad personal knowledge question | `alcove search{home_part} "query" --json`, then inspect returned OKF/source/mount/connector refs | none |\n'
        f"| Current managed KB inbox review | `alcove inbox{home_part} --kb <kb-name> peek --json`; read full item before summarizing if truncated | archive/note/todo/delete only after explicit confirmation |\n"
        f"| Save copied article or discussion note | search first for duplicates and choose target KB | `alcove inbox{home_part} --kb <kb-name> manual-add ...` or `alcove knowledge ...` |\n"
        f'| Save stable reference, preference, command, shortcut | `alcove pin{home_part} search "query" --json` | `alcove pin{home_part} add/update ...` |\n'
        f'| Save reusable prompt | `alcove prompt{home_part} search "query" --json` | `alcove prompt{home_part} save ...` |\n'
        "| Track todo, idea, routine, project, mount, connector | list/search the matching module first | use the matching `alcove task/idea/routine/project/mount/connector` command |\n"
        f"| Check monitored blogs now | `alcove blog{home_part} list --status '' --json`, then `alcove blog{home_part} check --json` or `alcove blog{home_part} check <source-id> --json` | only add/update sources after explicit confirmation |\n"
        f"| Run an information radar | `alcove radar{home_part} list --json`, then `alcove radar{home_part} status <radar-id> --json` | `alcove radar{home_part} run <radar-id> --json`, `--force --ai --notify`, or `--skip-fetch --force --ai --notify` after choosing an existing definition |\n\n"
        "## Blog Monitor Protocol\n\n"
        "- Use `alcove blog check`, not `alcove service tick`, when the user asks to\n"
        "  actively check blogs now. `service tick` is a stale maintenance path and may\n"
        "  skip sources whose TTL has not expired.\n"
        "- For a failure alert or `needs_attention` source, first run\n"
        f"  `alcove blog{home_part} list --status '' --json`, inspect `last_error`, then run\n"
        f"  `alcove blog{home_part} check <source-id> --json` to retry that source immediately.\n"
        "- If the check captures new articles, summarize the returned `new_articles`,\n"
        "  capture paths, and notification status. If it still fails, report the stage,\n"
        "  source id, and latest error, then inspect the run/event files only as\n"
        "  diagnostic evidence.\n"
        "- Scheduled monitoring is deterministic and should not depend on the current\n"
        "  chat agent. If the user asks for an AI summary, synthesize it in chat from\n"
        f"  captured `post.md` / `summary.md`, or run `alcove blog{home_part} check --summary --json`\n"
        "  when they explicitly want the configured model summary path.\n\n"
        "## Radar Protocol\n\n"
        "- Use `alcove radar list --json` first; radar IDs are user data and must not be assumed.\n"
        f"- Use `alcove radar{home_part} status <radar-id> --json` to inspect latest reports and source health before rerunning.\n"
        f"- Use `alcove radar{home_part} run <radar-id> --json` for a normal active refresh.\n"
        f"- Use `alcove radar{home_part} run <radar-id> --force --ai --notify --json` when the user asks to rerun, refresh now, summarize with AI, and send configured notifications.\n"
        f"- Use `alcove radar{home_part} run <radar-id> --skip-fetch --force --ai --notify --json` when the user asks to analyze or resend already fetched results without touching external sources.\n"
        "- Radar runs fetch and score deterministically first. Optional `ai_summary` is post-report analysis only; it does not rewrite fetched items or scores.\n"
        "- Scheduled radar runs start Codex or Claude only when the radar definition explicitly enables `ai_summary`. If AI fails, Alcove should still notify with the deterministic report when notification is enabled.\n\n"
        "## Retrieval Model\n\n"
        "- For read-only questions, start with Alcove MCP/CLI search to discover candidates.\n"
        "- Treat search results as leads, not final truth.\n"
        "- For broad, ambiguous, cross-topic, or low-confidence questions, continue with AI-led investigation: inspect OKF indexes, domain/topic/tag pages, candidate records, source refs, connector fetch refs, mount refs, and local files as useful.\n"
        "- Use the model's reasoning to expand queries, compare records, and synthesize answers from the specific local evidence found.\n\n"
        "## Save Completion Response\n\n"
        "After saving a note, pin, prompt, project, task, mount, connector, or managed KB record, respond with a compact receipt. Keep the record title and storage path clearly separate:\n\n"
        "```text\n"
        "已保存到 <target>.\n"
        "标题：<record title exactly as stored>\n"
        "位置：<relative OKF path or absolute local path>\n"
        "分类：<domain/topic or module>; 标签：<tags if any>\n"
        "验证：<validation/search result, or 未运行 + reason>\n"
        "```\n\n"
        "- Do not present a full file path as the title.\n"
        "- Do not hide a file path behind a Markdown link whose label is the title when the user needs a storage receipt; show `标题` and `位置` as separate fields.\n"
        "- If a Markdown link is useful, make the label explicit, such as `打开文件`, and still include the title separately.\n"
        "- When reporting search verification, name the query that found the record if useful. If one query misses but another works, say that directly instead of implying universal search success.\n\n"
        "## Commands\n\n"
        "```sh\n"
        f"alcove kb{home_part} list --json\n"
        f'alcove search{home_part} "query" --json\n'
        f'alcove search{home_part} --kb <kb-name> "query" --json\n'
        f"alcove inbox{home_part} --kb <kb-name> peek --json\n"
        f'alcove pin{home_part} add "Title" --kind regular --summary "..." --content "..." --tag tag --json\n'
        f'alcove pin{home_part} search "query" --kind todo --json\n'
        f"alcove pin{home_part} render-html --json\n"
        f'alcove prompt{home_part} save "Prompt Name" --content "..." --tag prompt --json\n'
        f'alcove project{home_part} add alias /path/to/project --note "..." --json\n'
        f'alcove task{home_part} add "Task" --notes "..." --json\n'
        f"alcove mount{home_part} add /path/to/folder --name name --json\n"
        f'alcove connector{home_part} fetch "connectors/<id>#<path>" --json\n'
        f"alcove blog{home_part} list --status '' --json\n"
        f"alcove blog{home_part} check --json\n"
        f"alcove blog{home_part} check openai --json\n"
        f"alcove radar{home_part} list --json\n"
        f"alcove radar{home_part} status <radar-id> --json\n"
        f"alcove radar{home_part} run <radar-id> --json\n"
        f"alcove radar{home_part} run <radar-id> --force --ai --notify --json\n"
        f"alcove radar{home_part} run <radar-id> --skip-fetch --force --ai --notify --json\n"
        f"alcove export{home_part} global /path/to/backup --json\n"
        "```\n\n"
        "## Safety\n\n"
        "- Durable writes should go through Alcove CLI/MCP commands; direct file edits are repair fallbacks only.\n"
        "- After any direct edit to Alcove-owned data, run the nearest validate, refresh, scan, or rebuild command.\n"
        "- Search before creating duplicates when the user asks to remember something important.\n"
        "- Verify through the user's intended entry point: if they asked for 常用收藏/置顶收藏, confirm that collection pin contains the link plus its purpose, not just that pin search finds a standalone item.\n"
        "- For OKF knowledge records, `source_refs` are internal OKF/source references. Do not store arbitrary external URLs there; keep external links in the note body or in a supported `resource` field.\n"
        "- Do not treat a raw link as permission to process existing inbox items.\n"
        "- Do not store article summaries as prompts; prompts are reusable instructions.\n"
        "- Mutating managed KB actions require explicit user confirmation for the current item.\n"
    )


def _managed_kb_skill(default_kb: str, home_part: str) -> str:
    _ = default_kb
    return (
        "---\n"
        "name: alcove-kb\n"
        "description: Use inside an Alcove managed knowledge base for inbox review, OKF notes, validation, gardening, and KB-scoped search.\n"
        "type: project\n"
        "---\n\n"
        "# Alcove Managed KB\n\n"
        "Default to this KB for inbox/archive/current-KB wording. Use Alcove Home-wide search for personal knowledge wording.\n\n"
        "## Search Routing\n\n"
        "- `当前知识库`, `这个知识库`, `inbox`, `archive`, or `当前目录` means this managed KB.\n"
        "- `本地个人知识库`, `个人知识系统`, `全部资料`, `OKF`, `知识数据`, `汇总总结`, `查一下`, or `相关资料` means Alcove Home-wide search across managed KBs, pins, tasks, prompts, projects, mounts, and connectors unless the user asks to narrow scope.\n"
        "- Use Alcove MCP/CLI search as candidate discovery. Omit `workspace` for Home-wide search; pass this workspace only for explicit current-KB scope.\n"
        "- Search results are leads, not final truth. For broad, ambiguous, cross-topic, or low-confidence questions, continue with AI-led investigation over OKF indexes, domain/topic/tag pages, source refs, connector fetch refs, mount refs, archive provenance, and local files as useful.\n"
        "- Do not route generic `本地知识库` wording to unrelated global or project-specific tools unless the user explicitly names that tool.\n\n"
        "## Write Routing\n\n"
        "- Use Alcove CLI/MCP commands for durable writes: inbox actions, OKF notes, revisions, pins, tasks, prompts, projects, mounts, connectors, links, refreshes, and exports.\n"
        "- Direct file edits are repair fallbacks only. Run `alcove validate` or the nearest refresh/scan/rebuild command afterward.\n\n"
        "## Fallback Routing Without Skills\n\n"
        "| Intent | Read path | Governed write path |\n"
        "| --- | --- | --- |\n"
        f'| Broad personal knowledge question | `alcove search{home_part} "query" --json`, then inspect returned OKF/source/mount/connector refs | none |\n'
        f'| Current KB question | `alcove search{home_part} "query" --json` from this workspace | none |\n'
        f"| Inbox review | `alcove inbox{home_part} peek --json`; read full item before summarizing if truncated | archive/note/todo/delete only after explicit confirmation |\n"
        f"| Save copied article or discussion note | search first for duplicates | `alcove inbox{home_part} manual-add ...` or `alcove knowledge ...` |\n"
        f"| Revise existing OKF note | inspect the target OKF path first | `alcove knowledge{home_part} revise ...`, then `alcove validate{home_part} --json` |\n\n"
        "## Commands\n\n"
        "```sh\n"
        f'alcove search{home_part} "query" --json\n'
        f"alcove inbox{home_part} peek --json\n"
        f"alcove validate{home_part} --json\n"
        "```\n\n"
        "Do not save article summaries as prompts. Archive sources and notes into the managed KB unless the user explicitly asks for a reusable prompt.\n"
    )


def managed_kb_claude_artifacts(root: Path, kb: str) -> list[ProfileArtifact]:
    return [
        ProfileArtifact(
            root / ".claude" / "commands" / "inbox-peek.md",
            _managed_kb_inbox_peek_command(kb),
            _template_path("managed-kb/claude-commands/inbox-peek.md"),
        ),
        ProfileArtifact(
            root / ".claude" / "commands" / "into-kb.md",
            _managed_kb_into_kb_command(kb),
            _template_path("managed-kb/claude-commands/into-kb.md"),
        ),
        ProfileArtifact(
            root / ".claude" / "skills" / "notes-search" / "SKILL.md",
            _managed_kb_notes_search_skill(kb),
            _template_path("managed-kb/skills/notes-search/SKILL.md"),
        ),
        ProfileArtifact(
            root / ".claude" / "skills" / "social_post_manager" / "SKILL.md",
            _managed_kb_social_post_manager_skill(kb, root),
            _template_path("managed-kb/skills/social_post_manager/SKILL.md"),
        ),
    ]


def managed_kb_codex_artifacts(root: Path, kb: str) -> list[ProfileArtifact]:
    return [
        ProfileArtifact(
            root / ".agents" / "skills" / "notes-search" / "SKILL.md",
            _managed_kb_notes_search_skill(kb),
            _template_path("managed-kb/skills/notes-search/SKILL.md"),
        ),
        ProfileArtifact(
            root / ".agents" / "skills" / "social_post_manager" / "SKILL.md",
            _managed_kb_social_post_manager_skill(kb, root),
            _template_path("managed-kb/skills/social_post_manager/SKILL.md"),
        ),
    ]


def _managed_kb_entry_section(home: str, kb: str, home_part: str) -> str:
    _ = kb
    return f"""{ALCOVE_SECTION_START}
## Alcove Managed KB Entry

This directory is an Alcove managed knowledge base workspace. Keep this file
thin: Skills and commands hold the detailed workflows.

- Home: configured Alcove Home
- Current KB: this workspace; discover registered names with `alcove kb{home_part} list --json`
- Managed data here: `knowledge/`, `inbox/`, `archive/`, `todo/`
- Global data outside this repo: pins, prompts, projects, tasks, mounts, connectors, KB registry

Routing: `当前知识库`/`inbox` means this KB. `本地个人知识库`, `OKF`, `知识数据`,
`汇总总结`, or `查一下` means Home-wide search. Search returns candidate records;
inspect OKF paths, source refs, mount refs, connector fetches, or local files
before answering broad or nuanced questions. This is AI-led OKF/local-file investigation.
Writes: use Alcove CLI/MCP mutation commands. Direct file edits are repair
fallbacks only; validate afterward. Use unrelated tools only when explicitly named.

Common commands:

```sh
alcove search{home_part} "query" --json
alcove inbox{home_part} peek --json
alcove validate{home_part} --json
```

Inbox posts require explicit per-post confirmation before archive, note, todo,
or delete. A raw link means capture to inbox, not permission to process items.

Project skills: `social_post_manager`, `notes-search`, `alcove-kb`.

If a listed project skill is unavailable, use the commands above as fallback.
{ALCOVE_SECTION_END}
"""


def _managed_kb_inbox_peek_command(kb: str) -> str:
    _ = kb
    return """---
description: Peek the oldest Alcove inbox item, summarize it structurally, and wait for an explicit action.
allowed-tools: Read, Bash
---

Show the oldest pending inbox item without changing files.

Run:

```sh
alcove inbox peek --json
```

Then present:

- metadata: platform, title, date, source URL
- topic: one sentence
- core content: grouped bullets or a compact table
- key numbers / quoted short phrases
- TL;DR: 3-6 bullets

Rules:

- Do not archive, note, delete, todo, or peek the next item.
- If peek output is truncated, OCR-heavy, or too thin for a defensible summary,
  run `alcove inbox read <identifier> --full --json` for the same item before
  presenting the summary.
- Do not mechanically list image 1/image 2/image 3; synthesize the content.
- Wait for an explicit user action such as archive, note, todo, delete, or skip.
- If inbox is empty, say there is no pending item.
"""


def _managed_kb_into_kb_command(kb: str) -> str:
    _ = kb
    return """---
description: Archive the current inbox item into Alcove knowledge as a Source, optionally with a Knowledge Concept.
allowed-tools: Read, Bash, Glob, Grep
---

Process the inbox item that was just shown by `/inbox-peek`.

Use archive mode when the user says archive, store, or keep only the source:

```sh
alcove inbox archive <folder> <domain/topic> --summary "..." --json
```

Use note mode when the user says note, summarize into knowledge, concept, or
record notes:

```sh
alcove inbox note <folder> <domain/topic> --summary "..." --json
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
alcove validate --json
```
"""


def _managed_kb_notes_search_skill(kb: str) -> str:
    _ = kb
    return """---
name: notes-search
description: Use when searching, browsing, listing tags, checking recent items, or auditing tags in an Alcove managed knowledge base.
type: project
---

# Alcove Notes Search

This skill is read-only. Use Alcove MCP/CLI search for candidate discovery, then
continue with AI-led investigation when the question needs more than direct
matches. Do not call retired project-local search scripts.

## Routing

- Chinese requests such as `本地个人知识库`, `知识库`, `OKF`, `知识数据`, `汇总总结`,
  `查一下`, or `相关资料` mean Alcove Home-wide search across managed KBs, pins,
  tasks, prompts, projects, mounts, and connectors unless the user asks to
  narrow scope.
- `当前知识库`, `这个知识库`, `inbox`, `archive`, or `当前目录` means this managed KB.
- Omit `workspace` for Home-wide MCP search; pass this workspace only for
  explicit current-KB scope.
- Do not route generic `本地知识库` wording to unrelated global or project-specific
  tools unless the user explicitly names that tool.

## Investigation Model

- Treat search results as leads, not final truth.
- For broad, ambiguous, cross-topic, or low-confidence questions, inspect OKF
  indexes, domain/topic/tag pages, candidate records, source refs, connector
  fetch refs, mount refs, archive provenance, and local files as useful.
- Use the model's reasoning to expand queries, follow relationships, compare
  records, and synthesize answers from the local evidence found.
- This skill is read-only. Do not mutate files while investigating.

## Commands

```sh
alcove search "query" --json
alcove search --tags --json
alcove search --recent 20 --json
alcove search --tag <tag> --json
alcove search --topic <domain/topic> --json
alcove search --platform <platform> --json
alcove search --type "Knowledge Concept" --json
alcove search --tag-doctor --json
alcove search --unindexed --json
```

Search results include type, title, domain, topic, platform, date, published_at,
collected_at, updated_at, deleted_at, tags, confidence, status, resource, and
path. Use these lifecycle fields to decide whether a candidate is outdated.
For user-confirmed cleanup of a specific search result, run
`alcove knowledge delete <path> --json` first for preview, then rerun with
`--confirm` only after explicit confirmation. Use `archive/` only for
provenance tracing; `knowledge/` is the formal knowledge base.
"""


def _managed_kb_social_post_manager_skill(kb: str, root: Path) -> str:
    _ = (kb, root)
    return """---
name: social_post_manager
description: Use when capturing social/web links into an Alcove inbox or reviewing, summarizing, archiving, noting, deleting, or deferring managed-KB inbox items.
type: project
---

# Social Post Manager

This skill keeps the original social-media-posts workflow while routing all
knowledge behavior through Alcove and all capture behavior through Clipsmith.
Clipsmith project page: https://octopusgarage.github.io/clipsmith/

Clipsmith is the default capture adapter, not a hard dependency of Alcove.
Other collectors may be used when they write a compatible bundle or folder into
this knowledge base's `inbox/<platform>/<capture-id>/` path.
Alcove reads Clipsmith `capture.json.content_files` first, so OCR text files
declared by Clipsmith are reviewable without a separate Alcove-side OCR step.

## Capture Links

If the user sends a downloadable social or web link, default to capture into
inbox. Do not process existing inbox items just because a link was captured.

Expected capture flow:

```sh
clipsmith providers --json
clipsmith capture start "<url>" --state-dir /tmp/clipsmith-state
clipsmith validate-bundle "<bundle_dir>" --json
clipsmith capture finalize "<job_id_or_job_path>" "<bundle_dir>" --state-dir /tmp/clipsmith-state
clipsmith sink inbox "<bundle_dir>" . --json
```

Run the sink command from the managed KB root. If the agent is working from a
different directory, replace `.` with that KB workspace path.

Platform expectations:

- XiaoHongShu: `xhslink.com` or `xiaohongshu.com/explore/` -> `inbox/xhs/`
- X/Twitter: `x.com/` or `twitter.com/` -> `inbox/x/`
- WeChat: `mp.weixin.qq.com` or `weixin.qq.com` -> `inbox/wechat/`
- Generic web: normal article URLs -> `inbox/web/`

OCR and bundle repair belong in Clipsmith, not in this repository.

## Review Inbox

Peek:

```sh
alcove inbox peek --json
```

Read a selected item:

```sh
alcove inbox read <folder> --json
```

Classify for suggestions:

```sh
alcove inbox classify <folder> [domain/topic]
```

## Mutating Actions

Never mutate without explicit user authorization for the current item.

Archive as Source:

```sh
alcove inbox archive <folder> <domain/topic> --summary "..." --json
```

Write Source + Knowledge Concept:

```sh
alcove inbox note <folder> <domain/topic> --summary "..." --json
```

Move to todo:

```sh
alcove inbox todo <folder> "reason"
```

Delete:

```sh
alcove inbox delete <folder> --confirm
```

Add direct knowledge:

```sh
alcove knowledge add-note <domain/topic> "Title" --summary "..."
alcove knowledge add-question <domain/topic> "Question" --answer "..."
alcove knowledge add-entity <domain/topic> "Name" --kind tool --summary "..."
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
- Do not save article summaries as prompts; prompts are reusable instructions.
- Do not create `notes/`.
- Do not recreate retired project-local scripts.
- Run `alcove validate --json` after mutating knowledge.
"""


def skill_source_path(profile: str) -> Path | None:
    if profile == "hub":
        return _template_path("hub/skills/alcove-hub/SKILL.md")
    if profile == "managed-kb":
        return _template_path("managed-kb/skills/alcove-kb/SKILL.md")
    return None


def _template_path(relative: str) -> Path:
    return Path(__file__).resolve().parent / "profile_templates" / relative
