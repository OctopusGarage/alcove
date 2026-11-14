---
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

## Explicit action semantics

- `仅归档原文到 <domain>/<topic>` means `alcove inbox archive` only.
- `整理笔记并归档到 <domain>/<topic>` and `记录笔记并归档` mean
  `alcove inbox note` once. It creates knowledge and archives the original;
  do not run a second archive operation.
- `整理成笔记到 <domain>/<topic>` may refer to the current discussion,
  pasted text, or ideas without an original post. Inspect the requested material,
  search for duplicates, and use `alcove knowledge add-note <domain/topic>
  "Title" --summary "..."`. Leave the current inbox item unchanged unless
  separately authorized. Do not create an artificial inbox item for this request.
- Continue accepting older archive/note wording, but show the explicit labels
  when offering choices.
- Preserve substantive OCR content in notes and retain source references.
- Choose classification from the durable subject, not incidental OCR words.
  Reuse a topic only when it fits; otherwise register an appropriate topic with
  the supported taxonomy workflow before writing. Never silently fall back to
  an unrelated topic or `misc`.
