# Blog Playwright Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Alcove blog monitoring work unattended from launchd with real browser-based discovery, deterministic Clipsmith capture, Telegram failure alerts, and service-tick level verification.

**Architecture:** Alcove remains the scheduler/state/notification owner. Blog discovery gains a real `playwright` adapter that extracts article links from rendered pages. Clipsmith remains the capture adapter. AI agents are not invoked by the scheduled path; failures are persisted and notified so the user can manually trigger Codex/Claude diagnostics.

**Tech Stack:** Python 3.12, Alcove CLI/service tick, Playwright CLI through an external helper script, Clipsmith CLI/skills, pytest, gitleaks.

---

### Task 1: Browser Discovery Adapter

**Files:**
- Modify: `src/alcove/blog_monitor.py`
- Test: `tests/test_blog_monitor.py`

- [ ] Add a failing test that configures `discover_method="playwright"`, monkeypatches the browser extraction helper, and asserts the discovered articles preserve title, URL, and published date.
- [ ] Implement `_discover_playwright(source)` as a separate adapter from `_discover_html(source)`.
- [ ] Implement a helper that runs a browser extraction command and returns JSON items shaped as `{title,url,date}`.
- [ ] Keep `requests` discovery unchanged for simple pages and Anthropic.

### Task 2: Failure State And Alerts

**Files:**
- Modify: `src/alcove/blog_monitor.py`
- Test: `tests/test_blog_monitor.py`

- [ ] Add tests for discovery failure that assert the source status is updated to `needs_attention`, `last_error` is populated, a failure run is written, and a Telegram failure message is attempted when notify is enabled.
- [ ] Add a focused failure notification message with source, stage, URL, error, and suggested user action.
- [ ] Do not invoke Claude, Codex, or `claude -p` from the scheduled failure path.

### Task 3: Local Source Configuration And Docs

**Files:**
- Modify: `README.md`, `docs/entry-modes.md`, `docs/usage.md`, `docs/modules.md`, `docs/superpowers/specs/2026-07-11-blog-monitor-design.md`
- Modify local data: `~/.alcove/blog-monitor/sources/openai.yml`

- [ ] Update OpenAI examples to use `https://openai.com/news/engineering/` with `--discover playwright` and `/index/` link filtering.
- [ ] Document that failure alerts ask the user to manually trigger agent diagnostics.
- [ ] Update local OpenAI source config to use the same values.

### Task 4: Verification

**Files:**
- Existing tests and local data only.

- [ ] Run targeted tests for blog monitor.
- [ ] Run `scripts/check.sh`.
- [ ] Run real discovery for OpenAI and Anthropic.
- [ ] Run `alcove service tick --home ~/.alcove --json` to verify the launchd-level command path.
- [ ] If OpenAI cannot be discovered unattended, leave the source in `needs_attention` and confirm Telegram failure alert behavior instead of claiming success.
