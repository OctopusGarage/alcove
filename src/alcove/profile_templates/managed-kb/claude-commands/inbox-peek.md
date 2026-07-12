---
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
