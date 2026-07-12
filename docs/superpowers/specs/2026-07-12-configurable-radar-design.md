# Configurable Radar Design

## Goal

Add a generic radar capability to Alcove for periodic information discovery,
scoring, reporting, notification, and dashboard display.

Radar categories are user-defined data, not hard-coded product modules. Alcove
provides the generic runtime, source adapters, presets, validation, scheduling,
and UI surfaces. A radar such as `tech-news`, `world-news`, `stocks`, or
`sports-news` is an instance under `~/.alcove/radars/definitions/`.

## Product Model

```text
Alcove
├── Managed / mounted / connector knowledge bases
├── Pins
├── Tasks
├── Watchers and blog monitors
└── Radars
    ├── built from user-editable definitions
    ├── optionally initialized from packaged presets
    └── run through one generic pipeline
```

Radars answer a different question than existing modules:

- Watchers answer "did this known URL/feed change?"
- Blog monitor answers "did this known blog publish new articles, and should
  they be captured into a managed KB inbox?"
- Connectors answer "what is currently indexed from this external system?"
- Radars answer "what matters today across a configured set of sources, given a
  preference profile?"

Because of that, radars should reuse service scheduling, dashboard, usage logs,
Telegram notification, and AI eval infrastructure, but they should not be
implemented as blog sources or connectors.

## Configuration

User-owned radar definitions live under Alcove Home:

```text
~/.alcove/radars/
├── definitions/
│   ├── tech-news.yml
│   ├── world-news.yml
│   ├── stocks.yml
│   └── sports-news.yml
├── runs/
│   └── <radar-id>/<YYYY-MM-DD>/run.json
├── cache/
│   └── <radar-id>/<YYYY-MM-DD>/
│       ├── raw.json
│       ├── scored.json
│       └── report-data.json
├── reports/
│   └── <radar-id>/
│       ├── YYYY-MM-DD.md
│       └── YYYY-MM-DD.html
├── okf/
│   └── <radar-id>/index.md
└── events.jsonl
```

Packaged presets live in the project and are templates only:

```text
src/alcove/radars/presets/
├── tech-news.yml
└── world-news.yml
```

The project may ship `tech-news` and `world-news` presets because they are
broadly useful examples. User-specific categories such as `stocks` and
`sports-news` should be created in `~/.alcove/radars/definitions/` and should
not become hard-coded Alcove features.

## Definition Shape

Each radar definition is declarative YAML:

```yaml
schema: alcove/radar-definition/v1
id: tech-news
name: Tech News
status: active
schedule:
  enabled: true
  ttl_hours: 24
sources:
  - id: hackernews
    adapter: hackernews
    enabled: true
    limit: 30
  - id: github-trending
    adapter: github-trending
    enabled: true
    params:
      language: ""
profile:
  languages: [en, zh]
  interest_tags: [LLM, AI, Rust, open source]
  blocked_keywords: [sponsored, advertisement]
  min_score_threshold: 0.6
scoring:
  mode: hybrid
  ai_provider: claude
  ai_enabled_for_service: false
report:
  language: zh
  style: concise-briefing
  formats: [md, html]
notify:
  enabled: true
  channel: telegram
```

The same shape supports stocks or sports by changing source adapters, profile
keys, scoring instructions, and report style. Alcove should validate unknown
fields leniently enough for forward compatibility, but strict enough to catch
missing `id`, missing source `adapter`, invalid schedule values, and unsupported
notification channels.

## Generic Pipeline

`RadarModule.run(radar_id, options)` is the primary interface. Internally it
performs:

```text
load definition
  -> resolve enabled source adapters
  -> fetch raw candidates
  -> normalize to RadarItem
  -> deduplicate by stable source/url/title keys
  -> apply block rules and rule pre-score
  -> optionally run AI scoring and summarization
  -> build report data
  -> write markdown/html reports
  -> write run metadata, cache, events, and OKF index
  -> optionally notify
```

The public interface should stay small:

- `list()`
- `init_from_preset(preset_id, radar_id)`
- `upsert_definition(definition)`
- `run(radar_id, skip_fetch=False, force=False, ai=False)`
- `status(radar_id="")`

Source adapters satisfy one internal seam:

```text
fetch(definition, run_context) -> list[RadarItem]
```

Adapters are implementation details. They can use HTTP, RSS, public APIs,
Playwright, local exports, or future collector commands. Two or more adapters
make this seam worthwhile; the old `social-radar` project already has many
fetchers that can be migrated into this shape.

## Built-In Presets

Initial packaged presets:

```text
tech-news
├── Hacker News
├── GitHub Trending
├── Dev.to
├── Reddit technical subreddits
├── V2EX
├── Juejin
├── InfoQ
└── Lobsters

world-news
├── Google News RSS EN/CN
├── Reuters
├── BBC
├── CNN
└── Reddit news subreddits
```

Optional user definitions migrated from the local `social-radar` installation:

```text
stocks
├── Yahoo Finance
├── Finviz
├── Reddit stock subreddits
├── StockTwits
└── ARK articles / holdings

sports-news
└── user-selected sports RSS, website, or API adapters
```

High-friction Playwright sources such as X Trending, TikTok Trending, and Google
Trends should be available as adapters but default to disabled in presets unless
the user explicitly opts in.

## Scheduling and AI

The launchd-backed local service can run stale radars through:

```text
alcove service tick --home ~/.alcove
  -> radar stale run
```

Default unattended behavior should be deterministic and reliable:

- fetch enabled sources,
- apply rule scoring,
- write cache/run/report,
- notify success or failure when configured.

AI scoring and report composition are useful, but should be explicit:

- `scoring.ai_enabled_for_service: false` by default for packaged presets,
- manual Hub runs can pass `--ai`,
- a user-owned radar definition may enable AI for service runs on that machine.

This keeps normal installs lightweight while allowing the local owner to opt
into Claude-backed daily reports.

## Dashboard and Search

Dashboard should show radars generically:

- configured radar count,
- last run status,
- item count,
- passed threshold count,
- failed source count,
- latest report links,
- schedule freshness,
- notification status.

Dashboard must not assume fixed categories such as tech/news/stocks. It should
render whatever appears in `~/.alcove/radars/definitions/*.yml`.

Search should include radar reports and high-scoring items as leads. Radar
items are time-sensitive signals, not durable knowledge. If a radar item becomes
important, the user or agent can promote it into a managed KB source/note or a
pin through existing governed write paths.

## Migration from Social Radar

Migration should be explicit and reversible:

```sh
alcove radar import-social-radar ~/.social_radar --json
```

Mapping:

```text
~/.social_radar/config/preference_profile.json
  -> ~/.alcove/radars/definitions/tech-news.yml

~/.social_radar/config/news_preference_profile.json
  -> ~/.alcove/radars/definitions/world-news.yml

~/.social_radar/config/stock_preference_profile.json
  -> ~/.alcove/radars/definitions/stocks.yml

~/.social_radar/data/{radar,news_radar,stock_radar}/all_*.json
  -> ~/.alcove/radars/cache/<radar-id>/<date>/raw-or-scored.json

~/.social_radar/reports/**
  -> ~/.alcove/radars/reports/<radar-id>/
```

The migration should not import old MCP, TODO, or scheduler code. Alcove already
has stronger versions of those concepts.

## Validation and Evaluation

Deterministic tests should cover:

- definition load/save/validation,
- preset initialization,
- source adapter fixtures,
- deduplication,
- skip-fetch cache reuse,
- report generation,
- Telegram notification payload construction,
- service tick integration,
- dashboard snapshot rows,
- migration from representative `social-radar` fixtures.

AI eval should cover intent quality:

- A generic custom radar definition can be interpreted without hard-coded type
  assumptions.
- Built-in `tech-news` and `world-news` presets are useful defaults.
- User-owned `stocks` and `sports-news` definitions remain data, not product
  modules.
- Generated reports are concise, explain why items matter, and avoid unsupported
  investment advice.

## Non-Goals

- Do not create hard-coded `tech`, `news`, `stock`, or `sports` product modules.
- Do not make radars a managed KB replacement.
- Do not silently write radar items into durable OKF notes.
- Do not migrate the old `social-radar` MCP server, TODO system, or scheduler.
- Do not require Claude, Codex, or API keys for deterministic service runs.
