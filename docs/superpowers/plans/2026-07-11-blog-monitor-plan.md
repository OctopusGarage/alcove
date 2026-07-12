# Blog Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a generic blog monitoring pipeline for discovering new articles, optional capture into managed KB inboxes, and optional notification.

**Architecture:** Add a focused `BlogMonitorModule` with source registry, discovery, seen state, capture adapter, run logs, and events. Wire it into CLI and `service tick` without expanding MCP surface yet.

**Tech Stack:** Python 3.12 standard library, PyYAML, existing Alcove home/KB/runtime services, Clipsmith CLI/web skill when available.

---

### Task 1: Core Module

**Files:**
- Create: `src/alcove/blog_monitor.py`
- Test: `tests/test_blog_monitor.py`

- [ ] Add dataclasses for `BlogSource`, `BlogArticle`, and nested policy data.
- [ ] Implement source add/list/load/write under `~/.alcove/blog-monitor/sources`.
- [ ] Implement discovery methods: `requests`, `rss`, `atom`, `sitemap`, and `hn-search`.
- [ ] Implement `seed` to initialize seen URLs without capture or notification.
- [ ] Implement `check` to diff articles, update seen state, write run JSON, and write events.
- [ ] Implement optional Clipsmith capture through the `clipsmith-web` skill and `clipsmith sink directory`.
- [ ] Implement optional Claude summary and optional Telegram notification as best-effort opt-in steps.

### Task 2: CLI and Service

**Files:**
- Modify: `src/alcove/cli.py`
- Modify: `src/alcove/service.py`
- Modify: `pyproject.toml`

- [ ] Add `alcove blog add/list/seed/check`.
- [ ] Add `--skip-blogs` to `alcove service tick`.
- [ ] Call `BlogMonitorModule.check(stale_only=True)` during service tick.
- [ ] Add `src/alcove/blog_monitor.py` to strict mypy files.

### Task 3: Docs

**Files:**
- Modify: `README.md`
- Modify: `docs/entry-modes.md`
- Modify: `docs/modules.md`
- Modify: `docs/data-and-backup.md`

- [ ] Document local service blog monitoring.
- [ ] Document storage paths and custom `inbox_path`.
- [ ] Document OpenAI and Anthropic example commands.

### Task 4: Verification

**Commands:**

```sh
uv run ruff format src/alcove/blog_monitor.py src/alcove/cli.py src/alcove/service.py tests/test_blog_monitor.py
uv run ruff check src/alcove/blog_monitor.py src/alcove/cli.py src/alcove/service.py tests/test_blog_monitor.py
uv run mypy src/alcove/blog_monitor.py src/alcove/service.py
uv run pytest tests/test_blog_monitor.py tests/test_service.py -q --no-cov
scripts/check.sh
```

Manual local validation:

```sh
alcove blog add "Anthropic Engineering" https://www.anthropic.com/engineering --id anthropic --discover playwright --link-pattern /engineering/ --kb social_media_posts --inbox-path inbox/anthropic --capture --json
alcove blog add "OpenAI Engineering" https://openai.com/news/engineering/ --id openai --discover playwright --link-pattern /index/ --kb social_media_posts --inbox-path inbox/openai --capture --json
alcove blog seed anthropic --json
alcove blog seed openai --json
alcove blog check --stale --json
```
