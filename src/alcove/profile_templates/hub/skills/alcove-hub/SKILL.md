---
name: alcove-hub
description: Use when working from the Alcove hub workspace or routing personal knowledge, pins, projects, prompts, tasks, mounts, connectors, or managed KB operations.
type: project
---

# Alcove Hub

This is the high-level router for Alcove. Decide the storage target before writing.

## Intent Routing

- knowledge article, copied source, discussion note, archive: managed KB inbox/knowledge.
- ambiguous record, remember, save this: ask one clarifying question unless the target is obvious.
- tiny durable reference, command, preference, shortcut: `pin --kind regular`.
- collection wording such as 收藏, 常用收藏, or 置顶收藏: search existing pins first; if a matching collection pin such as 常用收藏 exists, update that existing collection pin instead of only creating a separate pin.
- when saving a link with user-provided purpose, use case, or why-it-matters context, preserve that context in the target pin; do not save only the bare URL.
- future practice or deeper-study item that should stay visible: `pin --kind todo`.
- reusable instruction or agent prompt: `prompt`.
- local repo/path shortcut: `project`.
- todo, reminder, routine, follow-up: `task` or `idea`.
- external folder or historical repo to search read-only: `mount`.
- exported/protocol data source such as Apple Notes or GitHub Stars: `connector`.
- blog monitoring, scheduled article checks, failure alerts, or phrases such as
  监控博客更新 / 检查博客文章有没有更新: `blog monitor`.
- information radar, daily briefing, 技术雷达, 新闻雷达, 股票雷达, 体育资讯: `radar`.
- Alcove feature work, maintenance, refactoring, docs alignment, tests, or
  phrases such as 优化 Alcove / 新增功能 / 修这个项目: route to the registered
  project/worktree, then apply that project's engineering rules. Do not save the
  request as a knowledge note unless the user explicitly asks for a note.

## Project Development Protocol

- Most Alcove development requests still start in the Hub. Before changing code,
  identify the target project and switch to its project entry so `AGENTS.md`,
  `CLAUDE.md`, hooks, and local skills are in scope.
- For each user-facing change, run an entry-mode impact check: Hub workspace,
  managed-KB workspace, global MCP/command hints, CLI, local service/dashboard,
  docs, smoke, and AI eval.
- Update `alcove-hub` when the feature changes how users should ask for,
  trigger, review, or save data from the Hub. Update managed-KB skills only for
  KB-local capture/inbox/OKF workflows. Keep global MCP lightweight unless a
  wider toolset is explicitly intended.
- If no entry change is needed, say why in the completion summary.

## Fallback Routing Without Skills

| Intent | Read path | Governed write path |
| --- | --- | --- |
| Broad personal knowledge question | `alcove search "query" --json`, then inspect returned OKF/source/mount/connector refs | none |
| Current managed KB inbox review | `alcove inbox --kb <kb-name> peek --json`; read full item before summarizing if truncated | archive/note/todo/delete only after explicit confirmation |
| Save copied article or discussion note | search first for duplicates and choose target KB | `alcove inbox --kb <kb-name> manual-add ...` or `alcove knowledge ...` |
| Save stable reference, preference, command, shortcut | `alcove pin search "query" --json` | `alcove pin add/update ...` |
| Save reusable prompt | `alcove prompt recommend "scenario" --json` and `alcove prompt propose ... --json` | `alcove prompt save --proposal-id <id>` after proposal review |
| Track todo, idea, routine, project, mount, connector | list/search the matching module first | use the matching `alcove task/idea/routine/project/mount/connector` command |
| Check monitored blogs now | `alcove blog list --status '' --json`, then `alcove blog check --json` or `alcove blog check <source-id> --json` | only add/update sources after explicit confirmation |
| Run an information radar | `alcove radar list --json`, then `alcove radar status <radar-id> --json` | `alcove radar run <radar-id> --json`, `--force --ai --notify`, or `--skip-fetch --force --ai --notify` after choosing an existing definition |

## Blog Monitor Protocol

- Use `alcove blog check`, not `alcove service tick`, when the user asks to
  actively check blogs now. `service tick` is a stale maintenance path and may
  skip sources whose TTL has not expired.
- For a failure alert or `needs_attention` source, first run
  `alcove blog list --status '' --json`, inspect `last_error`, then run
  `alcove blog check <source-id> --json` to retry that source immediately.
- If the check captures new articles, summarize the returned `new_articles`,
  capture paths, and notification status. If it still fails, report the stage,
  source id, and latest error, then inspect the run/event files only as
  diagnostic evidence.
- Scheduled monitoring is deterministic and should not depend on the current
  chat agent. If the user asks for an AI summary, synthesize it in chat from
  captured `post.md` / `summary.md`, or run `alcove blog check --summary --json`
  when they explicitly want the configured model summary path.

## Radar Protocol

- Use `alcove radar list --json` first; radar IDs are user data and must not be assumed.
- Use `alcove radar status <radar-id> --json` to inspect latest reports and source health before rerunning.
- Use `alcove radar run <radar-id> --json` for a normal active refresh.
- Use `alcove radar run <radar-id> --force --ai --notify --json` when the user asks to rerun, refresh now, summarize with AI, and send configured notifications.
- Use `alcove radar run <radar-id> --skip-fetch --force --ai --notify --json` when the user asks to analyze or resend already fetched results without touching external sources.
- Radar runs fetch and score deterministically first. Optional `ai_summary` is post-report analysis only; it does not rewrite fetched items or scores.
- Scheduled radar definitions may use `schedule.daily_time` and `schedule.timezone`; the local service should wait for that daily window and still run at most once per local date.
- Scheduled radar runs start Codex or Claude only when the radar definition explicitly enables `ai_summary`. If AI fails, Alcove should still notify with the deterministic report when notification is enabled.

## Prompt Library Protocol

- When the user describes a task and asks what prompt to use, run
  `alcove prompt recommend "<scenario>" --json` and present at most five
  numbered candidates with why they match. If the user chooses multiple
  candidates, use `alcove prompt compose "<scenario>" --json` or inspect the
  chosen prompts with `alcove prompt get`.
- When the user asks to save something into the prompt library, first act as the
  prompt-quality reviewer yourself. Do not treat the user wording as already
  reusable. Decide whether it is:
  - a reusable prompt;
  - source material that should be rewritten into a reusable prompt;
  - a duplicate or update to an existing prompt;
  - a managed KB note / article summary / raw chat fragment that should not
    become an active prompt.
- Before proposing, rewrite the candidate into a concise copy-ready prompt body.
  Preserve the user's goal and constraints, but remove one-off chat context,
  metadata-card headings, personal paths, stale project names, and vague
  instructions. If the title promises verification, rerun, hardening, codifying,
  or 固化/复跑, the prompt body must require concrete evidence, repeatable
  commands or steps, and durable follow-up artifacts.
- Search and recommend before writing:
  `alcove prompt recommend "<scenario>" --json`. If a similar prompt exists,
  prefer updating/merging it instead of creating a new prompt.
- Do not call `prompt save` directly. Run
  `alcove prompt propose "<title>" --content "..." --json`. Use
  `--ai-eval-provider codex` or `--ai-eval-provider claude` only when the user
  explicitly asks for a separate model review; otherwise the current agent's
  own review plus the proposal's built-in eval is the normal Hub path.
- Inspect `action`, `similar`, `warnings`, `evaluation`, and the optimized `request`.
  Prefer updating or merging existing prompts when the proposal recommends
  `update_existing` or `merge_into_existing`.
- The optimized `request.content` must be copy-ready prompt text. Usage timing,
  triggers, surfaces, outputs, tags, and source refs belong in metadata fields,
  not as record-card headings inside the prompt body.
- Inspect `evaluation.prompt_ai_eval.rounds`. A high-quality proposal should pass
  both `professional_quality` and `adversarial_reuse`. If `must_fix` is not
  empty, revise the prompt and run `prompt propose` again instead of saving.
- Only accept a proposal with `alcove prompt save --proposal-id <id> --json`
  after confirming it should become reusable prompt memory. Save rejects
  proposals whose `evaluation.verdict` is not `ready` or `update_existing`.
- After save/update, inspect `prompt_eval`. A `needs_review` verdict should only
  appear after explicit force writes or legacy repair; do not treat it as a
  polished active prompt.
- Use direct `alcove prompt save --force ...` only for explicit repair or
  operator-confirmed direct writes.
- Article summaries, one-off project notes, and raw chat dumps belong in a
  managed KB unless the reusable instruction has been extracted and proposed.

## Retrieval Model

- For read-only questions, start with Alcove MCP/CLI search to discover candidates.
- Treat search results as leads, not final truth.
- For broad, ambiguous, cross-topic, or low-confidence questions, continue with AI-led investigation: inspect OKF indexes, domain/topic/tag pages, candidate records, source refs, connector fetch refs, mount refs, and local files as useful.
- Use the model's reasoning to expand queries, compare records, and synthesize answers from the specific local evidence found.

## Save Completion Response

After saving a note, pin, prompt, project, task, mount, connector, or managed KB record, respond with a compact receipt. Keep the record title and storage path clearly separate:

```text
已保存到 <target>.
标题：<record title exactly as stored>
位置：<relative OKF path or absolute local path>
分类：<domain/topic or module>; 标签：<tags if any>
验证：<validation/search result, or 未运行 + reason>
```

- Do not present a full file path as the title.
- Do not hide a file path behind a Markdown link whose label is the title when the user needs a storage receipt; show `标题` and `位置` as separate fields.
- If a Markdown link is useful, make the label explicit, such as `打开文件`, and still include the title separately.
- When reporting search verification, name the query that found the record if useful. If one query misses but another works, say that directly instead of implying universal search success.

## Commands

```sh
alcove kb list --json
alcove search "query" --json
alcove search --kb <kb-name> "query" --json
alcove inbox --kb <kb-name> peek --json
alcove pin add "Title" --kind regular --summary "..." --content "..." --tag tag --json
alcove pin search "query" --kind todo --json
alcove pin render-html --json
alcove prompt recommend "scenario" --json
alcove prompt compose "scenario" --json
alcove prompt propose "Prompt Name" --content "..." --tag prompt --json
alcove prompt proposal <proposal-id> --json
alcove prompt save --proposal-id <proposal-id> --json
alcove project add alias /path/to/project --note "..." --json
alcove task add "Task" --notes "..." --json
alcove mount add /path/to/folder --name name --profile docs --json
alcove mount update name --profile docs --exclude "**/_build/**" --json
alcove mount scan name --dry-run --json
alcove mount scan name --json
alcove connector fetch "connectors/<id>#<path>" --json
alcove blog list --status '' --json
alcove blog check --json
alcove blog check <source-id> --json
alcove radar list --json
alcove radar status <radar-id> --json
alcove radar run <radar-id> --json
alcove radar run <radar-id> --force --ai --notify --json
alcove radar run <radar-id> --skip-fetch --force --ai --notify --json
alcove export global /path/to/backup --json
```

## Safety

- Durable writes should go through Alcove CLI/MCP commands; direct file edits are repair fallbacks only.
- After any direct edit to Alcove-owned data, run the nearest validate, refresh, scan, or rebuild command.
- Search before creating duplicates when the user asks to remember something important.
- Verify through the user's intended entry point: if they asked for 常用收藏/置顶收藏, confirm that collection pin contains the link plus its purpose, not just that pin search finds a standalone item.
- For OKF knowledge records, `source_refs` are internal OKF/source references. Do not store arbitrary external URLs there; keep external links in the note body or in a supported `resource` field.
- Do not treat a raw link as permission to process existing inbox items.
- Do not store article summaries as prompts; prompts are reusable instructions.
- Mutating managed KB actions require explicit user confirmation for the current item.
