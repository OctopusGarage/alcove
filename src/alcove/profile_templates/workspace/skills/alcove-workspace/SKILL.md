---
name: alcove-workspace
description: Use inside a lightweight Alcove business workspace for scoped personal knowledge, pins, tasks, ideas, and prompt reuse.
type: project
---

# Alcove Business Workspace

This is a lightweight business-scoped Alcove workspace. Read `.alcove-workspace.yml` first to learn the workspace id, default KB, tags, modules, and purpose.

## Operating Model

- Start searches inside this workspace's configured scope: preferred KBs, tags, and modules.
- For workspace-local documents, notes, and recall, use `alcove workspace okf ...` before falling back to Home-wide search.
- If scoped search is too narrow, say that you are expanding to Home-wide search and then inspect evidence before answering.
- For durable writes, use Alcove CLI/MCP commands and preserve the workspace tag or context from `.alcove-workspace.yml`.
- Use `workspace okf add-note/import-file/search` for scene-local knowledge; use `pin`, `task`, `idea`, and `prompt recommend/compose` for global reusable memory and planning.
- If the workspace OKF is not initialized, run `alcove workspace okf init <workspace-id> --json` before saving scene-local knowledge.
- Prompt saves must still use the governed propose/save flow; do not turn raw notes or chat fragments into prompts.
- Do not perform Hub-only administration from here by default. Installing entries, editing global MCP, changing services, export/backup, connector/mount administration, radar definitions, publisher configuration, and health fixes belong in the Hub unless the user explicitly authorizes the command.

## Common Commands

```sh
alcove workspace okf init <workspace-id> --json
alcove workspace okf add-note <workspace-id> <domain/topic> "Title" --summary "..." --json
alcove workspace okf import-file <workspace-id> ./documents/file.md --topic <domain/topic> --json
alcove workspace okf search <workspace-id> "query" --json
alcove search "query" --json
alcove search --kb <kb-name> "query" --json
alcove pin add "Title" --tag <workspace-id> --summary "..." --content "..." --json
alcove task add "Task" --tag <workspace-id> --json
alcove idea add "Idea" --tag <workspace-id> --json
alcove prompt recommend "scenario" --json
alcove prompt compose "scenario" --json
```

## Escalation

When a request is about Alcove-wide configuration or system maintenance, route it to the Hub workspace. If running a one-shot command is enough, use `alcove workspace run hub ...` from outside this session.
