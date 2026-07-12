# Apple Notes Module Publishers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand Apple Notes publishing beyond pins to include planner, prompt library, and project registry mirrors with cleaner Apple Notes formatting and eval coverage.

**Architecture:** Keep `PublisherModule` as the coordinator. Add deterministic render templates for `planner_digest`, `prompt_library`, and `project_registry`; make `init apple-notes` merge missing default targets without overwriting user-modified targets; improve Markdown-to-Apple-Notes HTML conversion so generated notes are readable on mobile.

**Tech Stack:** Python 3.12, YAML publisher definitions, macOS Notes JXA target adapter, pytest, shell smoke, Alcove AI eval packet.

---

### Task 1: Extend Default Apple Notes Targets

**Files:**
- Modify: `src/alcove/publishers.py`
- Test: `tests/test_publishers.py`

- [ ] **Step 1: Add tests for default target merge**

Add a test that initializes Apple Notes, manually removes new targets from the definition, reruns `init_apple_notes`, and expects missing targets to be restored while existing target configuration remains unchanged.

- [ ] **Step 2: Implement merge-on-init**

Change `PublisherModule.init_apple_notes()` so existing definitions are updated only by adding missing default targets. Return `status: updated` with added target ids when it modifies the definition, otherwise return `status: exists`.

- [ ] **Step 3: Run targeted tests**

Run `uv run pytest tests/test_publishers.py -q --no-cov`.

### Task 2: Add Planner, Prompt, and Project Renderers

**Files:**
- Modify: `src/alcove/publishers.py`
- Test: `tests/test_publishers.py`

- [ ] **Step 1: Add renderer tests**

Create fixture data for tasks, ideas, routines, prompts, and projects. Assert that default Apple Notes publishing creates five notes:
`Regular Pins`, `TODO Pins`, `Planner Digest`, `Prompt Library`, and `Project Registry`.

- [ ] **Step 2: Implement render templates**

Add source/template support:
- `tasks` + `planner_digest`
- `prompts` + `prompt_library`
- `projects` + `project_registry`

Render readable Markdown with short summaries, section counts, no raw internal ids, and compact `~` paths.

- [ ] **Step 3: Run targeted tests**

Run `uv run pytest tests/test_publishers.py tests/test_service.py -q --no-cov`.

### Task 3: Improve Apple Notes Formatting

**Files:**
- Modify: `src/alcove/publishers.py`
- Test: `tests/test_publishers.py`

- [ ] **Step 1: Add formatting quality tests**

Assert generated Apple Notes HTML uses headings, paragraphs, ordered lists, unordered lists, and emphasis tags instead of one `<div>` per plain-text line. Assert rendered Markdown includes blank lines between sections and avoids long undifferentiated blocks.

- [ ] **Step 2: Replace naive HTML conversion**

Improve `_markdown_as_html()` for the subset Alcove emits:
- `#` and `##` headings
- numbered list items
- bullet list items
- indented continuation lines
- paragraphs
- blank-line spacing
- basic bold labels

- [ ] **Step 3: Run targeted tests**

Run `uv run pytest tests/test_publishers.py -q --no-cov`.

### Task 4: Extend Smoke and AI Eval Evidence

**Files:**
- Modify: `scripts/verify/smoke-isolated.sh`
- Modify: `src/alcove/ai_eval.py`
- Modify: `tests/test_ai_eval.py`

- [ ] **Step 1: Update smoke assertions**

Expect publisher run to update five targets, unchanged run to skip five targets, and all five render files to exist. Add a `publisher-render-quality.json` fixture with formatting checks.

- [ ] **Step 2: Add AI eval packet evidence**

Include `publisher_render_quality` in `packet["evidence"]["smoke"]` and update publisher module questions to ask whether Apple Notes mirrors are visually scannable and not text dumps.

- [ ] **Step 3: Run smoke and AI eval**

Run `scripts/smoke.sh` and `ALCOVE_AI_EVAL_PROVIDER=none scripts/eval-ai.sh`.

### Task 5: Local Real Apple Notes Verification

**Files:**
- Modify: `docs/usage.md`
- Modify: `docs/data-and-backup.md`

- [ ] **Step 1: Document the five-note layout**

Update docs to show pins, planner, prompts, and projects under `iCloud/Alcove`.

- [ ] **Step 2: Install and publish on the local machine**

Run `uv tool install --reinstall --editable .`, then `alcove publish init apple-notes --home ~/.alcove --json`, then `alcove publish run apple-notes --home ~/.alcove --json`.

- [ ] **Step 3: Verify real Notes state**

Confirm Apple Notes returns five fixed notes under the expected folders and a second publish skips unchanged content.

- [ ] **Step 4: Run final gates**

Run `uv run pytest -q`, `uv run ruff check .`, and commit if all gates pass.
