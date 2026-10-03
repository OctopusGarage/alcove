# Inbox Oldest-Item Ordering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `alcove inbox peek` return the earliest captured pending item across platforms while preserving legacy directory-date ordering.

**Architecture:** Keep ordering inside `InboxModule`. Build a path-aware sort key from `capture.json.captured_at`, fall back to a legacy `YYYYMMDD` directory prefix, and place undated items last with deterministic platform/name tie-breakers. Parse metadata defensively so corrupt bundles cannot break inbox review.

**Tech Stack:** Python 3.12, `datetime`, JSON, pytest, Ruff, mypy

---

### Task 1: Lock Down Capture-Time Ordering

**Files:**
- Modify: `tests/test_inbox.py`

- [ ] **Step 1: Add a failing cross-platform stable-ID regression test**

```python
def test_peek_orders_stable_id_bundles_by_capture_time(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(
        tmp_path,
        "wechat",
        "wechat-a-lexically-first",
        {
            "post.md": "# Later\n\nbody",
            "capture.json": json.dumps({"captured_at": "2026-07-08T00:00:00Z"}),
        },
    )
    _write_post(
        tmp_path,
        "xhs",
        "xhs-z-lexically-last",
        {
            "post.md": "# Earlier\n\nbody",
            "capture.json": json.dumps({"captured_at": "2026-07-07T23:00:00Z"}),
        },
    )

    post = InboxModule(workspace).peek()

    assert post is not None
    assert post.name == "xhs-z-lexically-last"
    assert post.platform == "xhs"
```

- [ ] **Step 2: Run the regression test and verify the old lexical behavior fails**

Run:

```bash
uv run pytest tests/test_inbox.py::test_peek_orders_stable_id_bundles_by_capture_time -q
```

Expected: FAIL because `wechat-a-lexically-first` is returned.

- [ ] **Step 3: Add timezone and malformed-metadata coverage**

```python
def test_peek_normalizes_capture_time_offsets(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(
        tmp_path,
        "wechat",
        "wechat-later",
        {
            "post.md": "# Later\n\nbody",
            "capture.json": json.dumps({"captured_at": "2026-07-07T00:30:00Z"}),
        },
    )
    _write_post(
        tmp_path,
        "xhs",
        "xhs-earlier",
        {
            "post.md": "# Earlier\n\nbody",
            "capture.json": json.dumps({"captured_at": "2026-07-07T08:00:00+08:00"}),
        },
    )

    post = InboxModule(workspace).peek()

    assert post is not None
    assert post.name == "xhs-earlier"


@pytest.mark.parametrize(
    "capture_json",
    ["not-json", json.dumps({"captured_at": "not-a-timestamp"})],
)
def test_peek_falls_back_to_legacy_dates_for_invalid_capture_metadata(
    tmp_path, capture_json
):
    workspace = Workspace.init(tmp_path)
    _write_post(
        tmp_path,
        "wechat",
        "stable-id",
        {"post.md": "# Invalid metadata\n\nbody", "capture.json": capture_json},
    )
    _write_post(
        tmp_path,
        "web",
        "20260706-legacy",
        {"article.md": "# Legacy\n\nbody"},
    )

    post = InboxModule(workspace).peek()

    assert post is not None
    assert post.name == "20260706-legacy"
```

- [ ] **Step 4: Run the focused tests and confirm failures match missing behavior**

Run:

```bash
uv run pytest tests/test_inbox.py -k 'peek_' -q
```

Expected: capture-time tests FAIL under name-only sorting; existing legacy tests PASS.

### Task 2: Implement Defensive Path-Aware Ordering

**Files:**
- Modify: `src/alcove/inbox.py:1-125`

- [ ] **Step 1: Add datetime imports and replace the name-only sort key**

```python
from datetime import UTC, datetime


    def _entries(self) -> list[Path]:
        entries: list[Path] = []
        if not self.paths.inbox.exists():
            return entries
        for platform_dir in sorted(self.paths.inbox.iterdir(), key=lambda p: p.name):
            if not platform_dir.is_dir():
                continue
            for item in platform_dir.iterdir():
                if item.is_dir():
                    entries.append(item)
        return sorted(entries, key=self._sort_key)

    def _sort_key(self, entry: Path) -> tuple[datetime, str, str]:
        captured_at = self._capture_time(entry)
        if captured_at is None:
            captured_at = self._legacy_name_time(entry.name)
        return (
            captured_at or datetime.max.replace(tzinfo=UTC),
            entry.parent.name,
            entry.name,
        )

    def _capture_time(self, entry: Path) -> datetime | None:
        try:
            metadata = json.loads((entry / "capture.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(metadata, dict):
            return None
        value = metadata.get("captured_at")
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(UTC)

    def _legacy_name_time(self, name: str) -> datetime | None:
        match = re.match(r"^(\d{8})(?!\d)", name)
        if match is None:
            return None
        try:
            return datetime.strptime(match.group(1), "%Y%m%d").replace(tzinfo=UTC)
        except ValueError:
            return None
```

- [ ] **Step 2: Run focused inbox tests**

Run:

```bash
uv run pytest tests/test_inbox.py -q
```

Expected: PASS.

- [ ] **Step 3: Run static quality checks for touched files**

Run:

```bash
uv run ruff check src/alcove/inbox.py tests/test_inbox.py
uv run ruff format --check src/alcove/inbox.py tests/test_inbox.py
uv run mypy src/alcove/inbox.py
```

Expected: all commands exit 0 without diagnostics.

- [ ] **Step 4: Commit the implementation**

```bash
git add src/alcove/inbox.py tests/test_inbox.py
git commit -m "fix(inbox): order pending items by capture time"
```

### Task 3: Verify the Real Workspace and Full Repository

**Files:**
- No source changes expected

- [ ] **Step 1: Run the original real-workspace regression**

```bash
workspace=/Users/kingsonwu/programming/kingson4wu/entropy-nexus/social_media_posts
actual=$(uv run alcove inbox --workspace "$workspace" peek --json | jq -r '.identifier')
expected=$(find "$workspace/inbox" -mindepth 3 -maxdepth 3 -name capture.json -type f -print0 \
  | xargs -0 jq -s -r 'min_by(.captured_at) | (.platform + "/" + .id)')
test "$actual" = "$expected"
```

Expected: both values are `xhs/xhs-6ab5ec030000000019027df0` and the command exits 0.

- [ ] **Step 2: Run the full test suite**

Run:

```bash
uv run pytest
```

Expected: all tests pass and repository coverage remains at or above 80%.

- [ ] **Step 3: Run repository-wide lint and formatting checks**

Run:

```bash
uv run ruff check .
uv run ruff format --check .
```

Expected: both commands exit 0.

- [ ] **Step 4: Confirm a clean implementation branch**

Run:

```bash
git status --short
git log -3 --oneline
```

Expected: no uncommitted source/test changes; the implementation commit follows the design and plan commits.
