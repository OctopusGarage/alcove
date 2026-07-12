---
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
