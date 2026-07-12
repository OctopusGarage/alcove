# Blog Telegram Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Send Telegram notifications containing a new blog article's title, URL, and captured `summary.md` content.

**Architecture:** Keep notification inside `BlogMonitorModule`; derive article notification rows from captures after the capture step. Avoid changing source config shape or MCP surfaces.

**Tech Stack:** Python stdlib, pytest, existing Alcove CLI and BlogMonitorModule.

---

### Task 1: Telegram Payload Test

**Files:**
- Modify: `tests/test_blog_monitor.py`

- [x] **Step 1: Write the failing test**

Add a test that creates a fake captured inbox directory with `summary.md`, enables Telegram notification, monkeypatches `urlopen`, and asserts the outgoing JSON payload contains title, URL, and summary.

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_blog_monitor.py::test_blog_notify_sends_title_url_and_captured_summary -q --no-cov`

Expected before implementation: fail because `_notify` does not accept captures and does not read `summary.md`.

### Task 2: Implementation

**Files:**
- Modify: `src/alcove/blog_monitor.py`

- [x] **Step 1: Pass captures into notification**

Change `_check_one` so `_notify` receives `captures`.

- [x] **Step 2: Build article-specific Telegram body**

Read `summary.md` from captured inbox paths, compact it, and include it beneath each article link.

- [x] **Step 3: Keep graceful fallback**

If credentials are missing, channel is unsupported, or `summary.md` is missing, return/send a clear status without failing the monitor run.

### Task 3: Verification

**Files:**
- Modify: `docs/usage.md`
- Modify: `README.md`

- [x] **Step 1: Update docs**

Document that Telegram notifications can include captured article summaries.

- [x] **Step 2: Run targeted and full checks**

Run targeted pytest, ruff, mypy for blog monitor, and `scripts/check.sh`.
