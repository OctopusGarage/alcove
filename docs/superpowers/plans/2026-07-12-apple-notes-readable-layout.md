# Apple Notes Readable Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve Apple Notes publisher output so mirrored Alcove notes feel clearly separated, readable, and intentionally formatted on mobile.

**Architecture:** Keep publisher source data unchanged and improve only Markdown renderers plus the Apple Notes HTML bridge. Reuse existing publisher definitions, content hashes, smoke fixtures, and AI eval evidence.

**Tech Stack:** Python publisher module, pytest, shell smoke scripts, macOS Notes JXA verification.

---

### Task 1: Add Readable Section Markers

**Files:**
- Modify: `src/alcove/publishers.py`
- Test: `tests/test_publishers.py`

- [ ] Add emoji-aware title and section labels for pins, planner, prompts, and projects.
- [ ] Insert Markdown horizontal separators between major sections and between long item groups.
- [ ] Keep the generated Markdown valid and readable outside Apple Notes.
- [ ] Update unit tests to assert headers, separators, and no `Detail:` dump.

### Task 2: Preserve Apple Notes Rendering Quality

**Files:**
- Modify: `src/alcove/publishers.py`
- Test: `tests/test_publishers.py`

- [ ] Convert `---` separators into Apple Notes friendly block dividers.
- [ ] Keep headings, item titles, labels, bullets, and content blocks on separate lines after Notes imports the HTML.
- [ ] Verify the HTML converter does not emit ordered-list markup that Notes may flatten.

### Task 3: Expand Smoke and AI Eval Evidence

**Files:**
- Modify: `scripts/verify/smoke-isolated.sh`
- Modify: `tests/test_ai_eval.py`

- [ ] Extend publisher render quality checks with emoji headers and divider checks.
- [ ] Ensure `publisher_render_quality.status == "passed"` only when the readable layout signals are present.
- [ ] Keep AI eval packet evidence deterministic and independent of real Apple Notes.

### Task 4: Local Verification and Real Apple Notes Publish

**Files:**
- No persistent source files expected.

- [ ] Run targeted pytest and ruff checks.
- [ ] Run `scripts/smoke.sh`.
- [ ] Run `ALCOVE_AI_EVAL_PROVIDER=none scripts/eval-ai.sh`.
- [ ] Reinstall local editable CLI.
- [ ] Publish to `~/.alcove` Apple Notes targets.
- [ ] Read back real Apple Notes HTML through JXA and verify emoji headers, dividers, item blocks, and no `Detail:` dump.
- [ ] Run final gate and commit.
