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

## Action menu

Always display these choices, including the standalone-note reminder:

- `仅归档原文到 <domain>/<topic>`（保留原文和来源，不额外整理笔记）
- `整理笔记并归档到 <domain>/<topic>`（生成知识笔记，同时归档原文）
- `整理成笔记到 <domain>/<topic>`（适用于当前讨论、粘贴内容或零散想法；无需原帖，不自动归档当前帖子）
- `标记 todo <原因>`
- `删除`
- `跳过`

Both archive actions remove the current item from inbox. Note-and-archive is
one `alcove inbox note` operation; never describe archive as a second step.
Standalone notes use `alcove knowledge add-note`, not `inbox note` or an
artificial inbox capture. Ask which material to save only when unclear.
Displaying this menu does not authorize any mutation.

## Local image text

Before summarizing images whose text contributes to the post, read trustworthy
existing OCR sidecars. If missing or incomplete, use the available Clipsmith OCR
skill to extract Chinese and English text locally and verify non-empty output.
Do not substitute model vision or image uploads for OCR. Inspect images visually
only for material non-text details or after local OCR fails; explain the fallback
and distinguish OCR text from visual interpretation.
