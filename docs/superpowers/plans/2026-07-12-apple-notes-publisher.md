# Apple Notes Publisher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a generic publisher module that renders active pins into two stable Apple Notes under a configurable Alcove folder.

**Architecture:** Add a new `alcove.publishers` module with definition/state parsing, source rendering, target adapter abstraction, and Apple Notes JXA implementation. Wire it into CLI and `service tick` while keeping Apple Notes connector read-only.

**Tech Stack:** Python 3.12, YAML/JSON state files, existing `PinsModule`, macOS `osascript -l JavaScript`, pytest with fake adapter, existing launchd service tick.

---

### Task 1: Publisher Core

**Files:**
- Create: `src/alcove/publishers.py`
- Test: `tests/test_publishers.py`

- [ ] **Step 1: Write core tests**

Add tests that create pins, initialize the default Apple Notes publisher, run it
with a fake target adapter, assert two target outputs, assert state is recorded,
and assert the second run skips unchanged content.

- [ ] **Step 2: Implement core types**

Create dataclasses for publisher definition, target definitions, state records,
target references, and target results. Implement YAML load/write helpers under
`~/.alcove/publishers/`.

- [ ] **Step 3: Implement pins renderer**

Use `PinsModule.list(status="active")`, filter by `kind`, sort with existing pin
ordering, and render deterministic Markdown text with Singapore time in the
header, count, priority sections, summaries, tags, resources, and content.

- [ ] **Step 4: Implement publish run orchestration**

For each enabled target, render content, calculate `sha256`, skip if unchanged,
otherwise resolve/create target, replace note body, write render artifact, state,
run record, and event.

### Task 2: Apple Notes Target Adapter

**Files:**
- Modify: `src/alcove/publishers.py`
- Test: `tests/test_publishers.py`

- [ ] **Step 1: Add fake-adapter tests for target errors**

Cover ambiguous title lookup, missing stateful note, and recreate-missing
behavior.

- [ ] **Step 2: Implement Apple Notes adapter protocol**

Expose `resolve_or_create(folder_path, title, note_id, recreate_missing)` and
`replace_note_body(note_id, title, body)`. Keep destructive operations out of
scope.

- [ ] **Step 3: Implement local JXA adapter**

Use `osascript -l JavaScript` to list folders/notes, create nested folders,
create notes, fetch by id, and replace body then reapply title. Return
machine-readable errors for macOS/permission/ambiguity/missing failures.

### Task 3: CLI and Service Tick

**Files:**
- Modify: `src/alcove/cli.py`
- Modify: `src/alcove/service.py`
- Test: `tests/test_publishers.py`
- Test: `tests/test_service.py`

- [ ] **Step 1: Add CLI parser tests**

Assert `alcove publish init apple-notes --home <tmp> --json`, `alcove publish
list --home <tmp> --json`, and `alcove publish run apple-notes --home <tmp>
--json` work with a fake target adapter hook.

- [ ] **Step 2: Add CLI commands**

Add `publish init/list/run` commands. `init apple-notes` writes the default
definition. `run` accepts optional `--target`.

- [ ] **Step 3: Add service tick integration**

Add `run_publishers` parameter and `--skip-publishers`. Service tick should run
stale publishers before OKF/health/dashboard and include a `publishers` payload.

### Task 4: Docs, Smoke, and Local Setup

**Files:**
- Modify: `README.md`
- Modify: `docs/data-and-backup.md`
- Modify: `docs/usage.md`
- Modify: `scripts/verify/smoke-isolated.sh`
- Modify: `src/alcove/ai_eval.py`

- [ ] **Step 1: Document publisher usage**

Add concise usage commands and explain Apple Notes generated notes are readable
mirrors, not source data.

- [ ] **Step 2: Add smoke coverage**

Add isolated smoke commands that initialize and run the publisher with fake
adapter behavior and verify render/state artifacts exist.

- [ ] **Step 3: Add AI eval evidence**

Add publisher smoke evidence to local AI eval prompts so future agents catch
broken publish flows.

### Task 5: Verification and Local Real Run

**Files:**
- No source files unless verification exposes a bug.

- [ ] **Step 1: Run focused tests**

Run `uv run pytest tests/test_publishers.py tests/test_service.py -q --no-cov`.

- [ ] **Step 2: Run lint**

Run `uv run ruff check src/alcove/publishers.py src/alcove/cli.py src/alcove/service.py tests/test_publishers.py tests/test_service.py`.

- [ ] **Step 3: Run smoke**

Run `scripts/smoke.sh`.

- [ ] **Step 4: Install local editable CLI and run real init**

Run `uv tool install --reinstall --editable .`, then `alcove publish init
apple-notes --home ~/.alcove --json`.

- [ ] **Step 5: Run real Apple Notes publish**

Run `alcove publish run apple-notes --home ~/.alcove --json` on macOS. If Notes
automation permission is missing, report the explicit error and leave state
unchanged.
