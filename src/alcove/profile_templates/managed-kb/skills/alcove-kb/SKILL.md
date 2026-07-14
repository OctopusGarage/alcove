---
name: alcove-kb
description: Use inside an Alcove managed knowledge base for inbox review, OKF notes, validation, gardening, and KB-scoped search.
type: project
---

# Alcove Managed KB

Default to this KB for inbox/archive/current-KB wording. Use Alcove Home-wide search for personal knowledge wording.

## Search Routing

- `当前知识库`, `这个知识库`, `inbox`, `archive`, or `当前目录` means this managed KB.
- `本地个人知识库`, `个人知识系统`, `全部资料`, `OKF`, `知识数据`, `汇总总结`, `查一下`, or `相关资料` means Alcove Home-wide search across managed KBs, pins, tasks, prompts, projects, mounts, and connectors unless the user asks to narrow scope.
- Use Alcove MCP/CLI search as candidate discovery. Omit `workspace` for Home-wide search; pass this workspace only for explicit current-KB scope.
- Search results are leads, not final truth. For broad, ambiguous, cross-topic, or low-confidence questions, continue with AI-led investigation over OKF indexes, domain/topic/tag pages, source refs, connector fetch refs, mount refs, archive provenance, and local files as useful.
- Do not route generic `本地知识库` wording to unrelated global or project-specific tools unless the user explicitly names that tool.

## Write Routing

- Use Alcove CLI/MCP commands for durable writes: inbox actions, OKF notes, revisions, pins, tasks, prompts, projects, mounts, connectors, links, refreshes, and exports.
- Direct file edits are repair fallbacks only. Run `alcove validate` or the nearest refresh/scan/rebuild command afterward.
- Mounted repository indexes are policy-filtered knowledge indexes. Use mount refs for README/docs/notes evidence; use `rg` or direct source reads for code-specific questions.

## Fallback Routing Without Skills

| Intent | Read path | Governed write path |
| --- | --- | --- |
| Broad personal knowledge question | `alcove search "query" --json`, then inspect returned OKF/source/mount/connector refs | none |
| Current KB question | `alcove search "query" --json` from this workspace | none |
| Inbox review | `alcove inbox peek --json`; read full item before summarizing if truncated | archive/note/todo/delete only after explicit confirmation |
| Save copied article or discussion note | search first for duplicates | `alcove inbox manual-add ...` or `alcove knowledge ...` |
| Revise existing OKF note | inspect the target OKF path first | `alcove knowledge revise ...`, then `alcove validate --json` |

## Commands

```sh
alcove search "query" --json
alcove inbox peek --json
alcove validate --json
```

Do not save article summaries as prompts. Archive sources and notes into the managed KB unless the user explicitly asks for a reusable prompt.
