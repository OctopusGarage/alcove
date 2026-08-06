# Configurable Radars

Radars are user-configured information briefings. Alcove provides the generic
engine, adapters, reports, scheduling, and dashboard projection. Radar
categories such as tech news, world news, stocks, sports, or
personal hobbies are user data under `~/.alcove/radars/definitions/`.

## Model

```text
~/.alcove/radars/
├── definitions/*.yml          one radar definition per user-configured radar
├── cache/<radar-id>/<date>/   fetched and scored item cache
│   ├── raw.json
│   ├── scored.json
│   └── raw.json               deterministic fetched source data
├── runs/<radar-id>/<date>/run.json
├── reports/<radar-id>/<date>.md
├── reports/<radar-id>/<date>.html
├── reports/<radar-id>/<date>.ai.md   optional AI summary artifact
├── okf/<radar-id>/index.md    derived OKF-readable latest-run index
├── proposals/*.json           governed action proposals derived from runs
├── proposals/index.json       derived proposal status index
└── events.jsonl
```

Each definition is YAML using `schema: alcove/radar-definition/v1`. Important
fields:

- `id`, `name`, `status`
- `sources[]`: `id`, `adapter`, `enabled`, `limit`, `params`
- `profile`: interests, regions, languages, blocked keywords, thresholds
- `scoring`: deterministic or future AI-assisted scoring preferences
- `report`: language, style, output formats
- `ai_summary`: optional post-report AI analysis through `codex exec` or
  `claude -p`
- `schedule`: enabled flag, optional local daily run time, timezone, and TTL
  fallback for `alcove service tick`
- `notify`: optional notification policy for Telegram, Feishu webhook, or TCB sinks

Built-in presets are only starter templates:

```sh
alcove radar preset list --json
alcove radar init tech-news --from-preset tech-news --json
alcove radar init world-news --from-preset world-news --json
alcove radar init stocks --from-preset stocks --json
alcove radar init sports-news --from-preset sports-news --json
```

The packaged starters currently cover technology news, world news, market/stock
signals, and sports news. They are still user-editable definitions once
installed; the engine remains generic.

Custom radars should be saved as user definitions. The product code must not
assume fixed IDs such as `stocks` or `sports-news`.

## Run And Query

```sh
alcove radar list --json
alcove radar run <radar-id> --json
alcove radar run <radar-id> --ai --notify --json
alcove radar run <radar-id> --skip-fetch --force --ai --notify --json
alcove radar status <radar-id> --json
alcove radar explain <radar-id> --query "story title or URL" --json
```

`radar run` fetches enabled sources, deduplicates by URL/title, scores with the
definition profile, writes cache, writes Markdown/HTML reports, writes a latest
OKF index, and appends a run event.

`radar explain` is a read-only diagnostic for support/debugging. It reads the
existing `raw.json`, `scored.json`, and `run.json` artifacts for the latest run
or a selected `--date YYYY-MM-DD`; it never fetches sources or invokes AI. Use
it when an expected story is missing from a report:

```sh
alcove radar explain sports-news \
  --query "Spain defeat France" \
  --date 2026-07-29 \
  --json
```

The response reports the likely pipeline stage, matched raw/scored rows,
`source_id`, score, `score_reason`, `included`, final report presence, source
failure context, and compact artifact paths. Stages are diagnostic evidence:
absence from cache can mean the source failed, the upstream feed did not contain
the story, or the query did not match the cached title/URL/summary exactly. If
the selected date has no `run.json`, the stage is `no_run` and the missing
artifact paths are included.

## Governed Action Proposals

Action proposals are an explicit confirmation boundary between radar evidence
and global planner/prompt writes. They are extracted only from an existing
`run.json`, its `scored.json`, report paths, radar OKF index, and source URLs;
generation does not fetch sources or write a task, idea, or prompt.

```sh
alcove radar proposal generate <radar-id> --date YYYY-MM-DD --action-type idea --json
alcove radar proposal list --status pending --json
alcove radar proposal get <proposal-id> --json
alcove radar proposal accept <proposal-id> --json
alcove radar proposal defer <proposal-id> --json
alcove radar proposal reject <proposal-id> --json
```

Each proposal stores a stable `run_id`, source URL, scored/report/OKF paths,
source adapter, deduplication key, and lifecycle status: `pending`, `accepted`,
`rejected`, `deferred`, or `duplicate`. Duplicate extraction is idempotent.
Acceptance records the resulting task/idea/prompt ID and can be repeated safely;
the second acceptance returns an idempotent receipt without creating another
target. MCP exposes read-only list/get in `lite`; extraction and confirmation
tools are available in the full toolset. The dashboard snapshot includes
proposal rows and pending counts.

`alcove service tick` runs only active definitions with `schedule.enabled: true`.
Definitions may set a local daily trigger:

```yaml
schedule:
  enabled: true
  daily_time: "10:00"
  timezone: Asia/Singapore
  ttl_hours: 24
```

When `daily_time` is set, it is the earliest local execution time. A completed
run remains fresh until `run_at + ttl_hours`; a fresh successful run is skipped
and reported as healthy even when it crosses a local date boundary. Once that
success expires, the radar runs on the first service tick at or after
`daily_time`. A missing, malformed, or non-completed run is not considered a
successful run. Without `daily_time`, Alcove runs the first tick after the
latest successful run expires.

Skipped radar health rows include the last run status and timestamp. When the
last run was unsuccessful, they also include source-level errors or the stored
run error so the health notification can identify what needs investigation.
Scheduled runs are deterministic unless the radar definition explicitly enables
`ai_summary.enabled: true`. When AI summary is enabled, Alcove calls the
configured provider after the deterministic report is already written:

```yaml
ai_summary:
  enabled: true
  provider: codex        # codex | claude
  timeout_seconds: 180
  max_input_chars: 12000
  prompt: >
    Use a radar-specific prompt here. Tech, world news, market, sports, and
    custom radars should not share one generic summarization prompt.
notify:
  enabled: true
  sinks:
    - type: telegram
    - type: tcb
      channel: lark
      document_formats: [md, html]
  include_ai_summary: true
  include_top_links: true
```

The AI step is a post-processing layer. It does not change fetched items,
deterministic scores, thresholds, or source evidence. If AI fails, the run still
sends the deterministic report when notifications are enabled and records the AI
error in `run.json`.

Notification behavior:

- `notify.enabled: true` sends notifications for completed and partially failed
  runs. Legacy `channel: telegram` remains supported; new definitions should
  prefer `sinks[]`.
- Supported sinks:
  - `telegram`: sends the summary message and, when available, sends both the
    Markdown and HTML report files as Telegram documents.
  - `feishu`: sends a Feishu custom bot text message through a webhook. The
    message includes status, AI/deterministic summary, and top links. Feishu
    custom bot webhooks do not upload local files, so local report paths are not
    included in the message.
  - `tcb`: sends notification text and report files through a running
    [`tmux-claude-bot`](https://github.com/OctopusGarage/tmux-claude-bot)
    service using `tcb notify --attach`. This is the preferred Feishu/Lark
    attachment path.
- Notification text does not include local report paths. Channels with document
  upload support should send report files as attachments instead of exposing
  local filesystem paths in chat.
- Source failures are visible as `completed_with_errors` and are included in
  `run.json`.
- AI summary failure falls back to a deterministic briefing instead of blocking
  the notification.
- `--notify` forces notification for a manual run even if the definition keeps
  `notify.enabled: false`.

Feishu sink configuration:

```yaml
notify:
  enabled: true
  sinks:
    - type: feishu
      webhook_env: ALCOVE_FEISHU_WEBHOOK_URL
      secret_env: ALCOVE_FEISHU_SECRET   # optional signed bot secret
```

`webhook` and `secret` may also be set directly in a local-only definition, but
environment variables in `~/.alcove/.env` are preferred for secrets.

Feishu/Lark attachment configuration through `tmux-claude-bot`:

```yaml
notify:
  enabled: true
  sinks:
    - type: tcb
      channel: lark      # telegram | lark | both
      session: <project-session>  # route Lark delivery to the session-bound group
      document_formats: [md, html]
```

This requires
[`tmux-claude-bot`](https://github.com/OctopusGarage/tmux-claude-bot) to be
installed and running with the desired chat adapter configured. Alcove delegates
file upload to `tcb notify --attach`, so it does not need Feishu app credentials
or Telegram tokens for this sink.

Hub/manual patterns:

- Fresh rerun and AI notification:
  `alcove radar run tech-news --force --ai --notify --json`
- Analyze already fetched cache without touching sources:
  `alcove radar run tech-news --skip-fetch --force --ai --notify --json`
- Normal scheduled path:
  `alcove service tick --home ~/.alcove --json`

## Quality Evaluation

Radar changes are covered by a dedicated report smoke:

```sh
scripts/smoke-radar-reports.sh
```

The suite creates deterministic examples for `tech-news`, `world-news`,
`stocks`, and `sports-news`, generates Markdown and HTML reports, checks report
structure and source diversity, opens each report in desktop and mobile
Chromium when Playwright is available, and writes evidence to
`.tmp/radar-reports/radar-reports-report.json`.

`scripts/eval-ai.sh` includes this artifact in the AI review packet so Codex or
Claude can judge both report content quality and browser presentation.

## Source Adapters

Current source adapters:

- `fixture`: deterministic JSON list for tests and local custom radars.
- `rss`: RSS/Atom feeds.
- `generic-html`: simple link extraction from an HTML page.
- `hackernews`: Hacker News Firebase top stories.
- `github-trending`: GitHub Trending repository cards.

Adapters are generic. A radar definition chooses adapters through `sources[]`;
categories remain user data.

## Agent Rules

- Read path: agents may inspect radar definitions, run status, reports, cache,
  and OKF indexes to answer user questions.
- Write path: durable changes should use `alcove radar init`,
  `alcove radar run`, or a controlled definition save path.
- Scheduled path: launchd/service runs deterministic fetch/score/report first,
  then optional `ai_summary`/Telegram post-processing only when the definition
  explicitly enables it.
- AI path: Hub/agent sessions may force reruns, analyze cached reports with
  `--skip-fetch --force --ai --notify`, adjust definitions, or investigate
  failures with explicit user intent.
