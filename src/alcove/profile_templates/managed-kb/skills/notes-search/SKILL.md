---
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
