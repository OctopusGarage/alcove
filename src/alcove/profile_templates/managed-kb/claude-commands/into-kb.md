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
