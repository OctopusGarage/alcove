# Configurable Radar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a generic, user-configurable radar module to Alcove so users can define daily information radars such as tech news, world news, stocks, or sports without hard-coding those categories as product modules.

**Architecture:** Implement a deep `RadarModule` with a small public interface over definition storage, preset initialization, source adapters, scoring/report generation, run history, service scheduling, dashboard/search projection, and social-radar migration. Built-in `tech-news` and `world-news` are packaged presets; `stocks` and `sports-news` are user-owned definitions under `~/.alcove/radars/definitions/`.

**Tech Stack:** Python 3.12, stdlib `urllib`/`html.parser`/`xml.etree`, PyYAML, existing Alcove `AlcoveHome`, `UsageRecorder`, dashboard snapshot pipeline, pytest, mypy strict.

---

## File Structure

```text
src/alcove/radars/
├── __init__.py                      exports RadarModule and request models
├── models.py                        dataclasses, schema constants, validation helpers
├── module.py                        public RadarModule interface and filesystem storage
├── pipeline.py                      run orchestration, cache/report/event writes
├── scoring.py                       rule score and optional Claude scoring adapter
├── reporting.py                     markdown/html report rendering
├── migration.py                     explicit ~/.social_radar migration
├── sources/
│   ├── __init__.py                  source adapter registry
│   ├── base.py                      SourceAdapter interface and fetch context
│   ├── rss.py                       RSS/Atom adapter using stdlib XML
│   ├── hackernews.py                HN top stories adapter
│   ├── github_trending.py           GitHub Trending HTML adapter
│   ├── reddit.py                    configurable subreddit adapter
│   ├── generic_html.py              link-pattern HTML adapter
│   ├── finance.py                   basic Yahoo/Finviz style stock adapters
│   └── fixture.py                   deterministic adapter for tests/custom imports
└── presets/
    ├── tech-news.yml
    └── world-news.yml

tests/
├── test_radars.py
├── test_radar_sources.py
├── test_radar_migration.py
├── test_radar_cli.py
├── test_radar_service.py
└── test_radar_dashboard.py
```

Modify:

```text
src/alcove/cli.py
src/alcove/service.py
src/alcove/dashboard.py
src/alcove/search_sources.py or src/alcove/search_global.py
src/alcove/ai_eval.py
src/alcove/profile_templates/hub/skills/alcove-hub/SKILL.md
docs/modules.md
docs/entry-modes.md
docs/usage.md
README.md
pyproject.toml
```

Do not move old `social-radar` code wholesale. Copy behavior only where it fits the generic adapter model.

---

### Task 1: Radar Models and Definition Storage

**Files:**
- Create: `src/alcove/radars/__init__.py`
- Create: `src/alcove/radars/models.py`
- Create: `src/alcove/radars/module.py`
- Test: `tests/test_radars.py`

- [ ] **Step 1: Write failing model/storage tests**

Create `tests/test_radars.py` with:

```python
from __future__ import annotations

import yaml

from alcove.home import AlcoveHome
from alcove.radars import RadarModule, RadarDefinition, RadarSource


def test_radar_definition_round_trips_as_user_data(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = RadarModule(home)

    definition = RadarDefinition(
        id="sports-news",
        name="Sports News",
        sources=[RadarSource(id="nba-rss", adapter="rss", params={"url": "https://example.com/rss"})],
        profile={"interest_tags": ["NBA"], "blocked_keywords": ["betting"]},
        report={"language": "zh", "style": "concise-briefing", "formats": ["md"]},
    )

    result = module.upsert_definition(definition)
    loaded = module.get("sports-news")

    assert result["status"] == "saved"
    assert result["definition"]["id"] == "sports-news"
    assert loaded.id == "sports-news"
    assert loaded.sources[0].adapter == "rss"
    assert (home.root / "radars/definitions/sports-news.yml").is_file()


def test_radar_definition_validation_rejects_missing_source_adapter(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    path = home.root / "radars/definitions/bad.yml"
    path.parent.mkdir(parents=True)
    path.write_text(
        yaml.safe_dump(
            {
                "schema": "alcove/radar-definition/v1",
                "id": "bad",
                "name": "Bad",
                "sources": [{"id": "broken"}],
            }
        ),
        encoding="utf-8",
    )

    module = RadarModule(home)

    try:
        module.get("bad")
    except ValueError as exc:
        assert "source adapter is required" in str(exc)
    else:
        raise AssertionError("expected invalid radar definition")


def test_radar_list_is_generic_and_does_not_assume_fixed_ids(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = RadarModule(home)
    module.upsert_definition(
        RadarDefinition(
            id="custom-ai-products",
            name="AI Product Radar",
            sources=[RadarSource(id="feed", adapter="rss", params={"url": "https://example.com/rss"})],
        )
    )

    payload = module.list()

    assert payload["count"] == 1
    assert payload["definitions"][0]["id"] == "custom-ai-products"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_radars.py -q --no-cov
```

Expected: import failure for `alcove.radars`.

- [ ] **Step 3: Implement models**

Create `src/alcove/radars/models.py`:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


RADAR_DEFINITION_SCHEMA = "alcove/radar-definition/v1"
RADAR_RUN_SCHEMA = "alcove/radar-run/v1"
DEFAULT_TTL_HOURS = 24


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class RadarSchedule:
    enabled: bool = False
    ttl_hours: int = DEFAULT_TTL_HOURS

    def as_dict(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "ttl_hours": max(int(self.ttl_hours), 1)}


@dataclass(frozen=True)
class RadarSource:
    id: str
    adapter: str
    enabled: bool = True
    limit: int = 30
    params: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "adapter": self.adapter,
            "enabled": self.enabled,
            "limit": max(int(self.limit), 0),
            "params": self.params,
        }


@dataclass(frozen=True)
class RadarDefinition:
    id: str
    name: str
    sources: list[RadarSource]
    schema: str = RADAR_DEFINITION_SCHEMA
    status: str = "active"
    schedule: RadarSchedule = field(default_factory=RadarSchedule)
    profile: dict[str, Any] = field(default_factory=dict)
    scoring: dict[str, Any] = field(default_factory=dict)
    report: dict[str, Any] = field(default_factory=dict)
    notify: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "schedule": self.schedule.as_dict(),
            "sources": [source.as_dict() for source in self.sources],
            "profile": self.profile,
            "scoring": self.scoring,
            "report": self.report,
            "notify": self.notify,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class RadarItem:
    source_id: str
    adapter: str
    title: str
    url: str
    summary: str = ""
    author: str = ""
    published_at: str = ""
    tags: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    score_reason: str = ""
    included: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
```

- [ ] **Step 4: Implement storage module**

Create `src/alcove/radars/module.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from alcove.home import AlcoveHome
from alcove.markdown import normalize_slug
from alcove.paths import compact_user_path
from alcove.radars.models import RadarDefinition, RadarSchedule, RadarSource, now_iso


class RadarModule:
    def __init__(self, home: AlcoveHome) -> None:
        self.home = home
        self.root = home.root / "radars"
        self.definitions_root = self.root / "definitions"
        self.cache_root = self.root / "cache"
        self.runs_root = self.root / "runs"
        self.reports_root = self.root / "reports"
        self.okf_root = self.root / "okf"
        self.events_path = self.root / "events.jsonl"

    def list(self, *, status: str = "active") -> dict[str, Any]:
        definitions = [
            definition.as_dict()
            for definition in self._load_definitions()
            if not status or definition.status == status
        ]
        return {"count": len(definitions), "definitions": definitions}

    def get(self, radar_id: str) -> RadarDefinition:
        normalized = normalize_slug(radar_id)
        path = self.definitions_root / f"{normalized}.yml"
        if not path.is_file():
            raise FileNotFoundError(f"Radar definition not found: {radar_id}")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Radar definition is invalid: {compact_user_path(path)}")
        return self._definition(data)

    def upsert_definition(self, definition: RadarDefinition) -> dict[str, Any]:
        normalized = normalize_slug(definition.id)
        if not normalized:
            raise ValueError("Radar id is required")
        timestamp = now_iso()
        existing_created_at = ""
        try:
            existing_created_at = self.get(normalized).created_at
        except FileNotFoundError:
            existing_created_at = timestamp
        saved = RadarDefinition(
            id=normalized,
            name=definition.name or normalized,
            sources=definition.sources,
            schema=definition.schema,
            status=definition.status or "active",
            schedule=definition.schedule,
            profile=definition.profile,
            scoring=definition.scoring,
            report=definition.report,
            notify=definition.notify,
            tags=definition.tags,
            created_at=existing_created_at,
            updated_at=timestamp,
        )
        self._validate(saved)
        self.definitions_root.mkdir(parents=True, exist_ok=True)
        path = self.definitions_root / f"{normalized}.yml"
        path.write_text(
            yaml.safe_dump(saved.as_dict(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return {"status": "saved", "path": compact_user_path(path), "definition": saved.as_dict()}

    def _load_definitions(self) -> list[RadarDefinition]:
        if not self.definitions_root.is_dir():
            return []
        definitions: list[RadarDefinition] = []
        for path in sorted(self.definitions_root.glob("*.yml")):
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(payload, dict):
                definitions.append(self._definition(payload))
        return definitions

    def _definition(self, payload: dict[str, Any]) -> RadarDefinition:
        schedule = payload.get("schedule") if isinstance(payload.get("schedule"), dict) else {}
        sources = payload.get("sources") if isinstance(payload.get("sources"), list) else []
        definition = RadarDefinition(
            id=str(payload.get("id") or ""),
            name=str(payload.get("name") or payload.get("id") or ""),
            status=str(payload.get("status") or "active"),
            schedule=RadarSchedule(
                enabled=bool(schedule.get("enabled", False)),
                ttl_hours=int(schedule.get("ttl_hours") or 24),
            ),
            sources=[
                RadarSource(
                    id=str(source.get("id") or ""),
                    adapter=str(source.get("adapter") or ""),
                    enabled=bool(source.get("enabled", True)),
                    limit=int(source.get("limit") or 30),
                    params=source.get("params") if isinstance(source.get("params"), dict) else {},
                )
                for source in sources
                if isinstance(source, dict)
            ],
            profile=payload.get("profile") if isinstance(payload.get("profile"), dict) else {},
            scoring=payload.get("scoring") if isinstance(payload.get("scoring"), dict) else {},
            report=payload.get("report") if isinstance(payload.get("report"), dict) else {},
            notify=payload.get("notify") if isinstance(payload.get("notify"), dict) else {},
            tags=[str(tag) for tag in payload.get("tags") or []],
            created_at=str(payload.get("created_at") or ""),
            updated_at=str(payload.get("updated_at") or ""),
        )
        self._validate(definition)
        return definition

    def _validate(self, definition: RadarDefinition) -> None:
        if not normalize_slug(definition.id):
            raise ValueError("Radar id is required")
        for source in definition.sources:
            if not source.id:
                raise ValueError("Radar source id is required")
            if not source.adapter:
                raise ValueError(f"Radar source adapter is required: {source.id}")
        channel = str(definition.notify.get("channel") or "telegram")
        if channel not in {"telegram"}:
            raise ValueError(f"Unsupported radar notify channel: {channel}")
```

Create `src/alcove/radars/__init__.py`:

```python
from alcove.radars.models import RadarDefinition, RadarItem, RadarSchedule, RadarSource
from alcove.radars.module import RadarModule

__all__ = ["RadarDefinition", "RadarItem", "RadarSchedule", "RadarSource", "RadarModule"]
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run pytest tests/test_radars.py -q --no-cov
uv run mypy src/alcove/radars/models.py src/alcove/radars/module.py
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/alcove/radars/__init__.py src/alcove/radars/models.py src/alcove/radars/module.py tests/test_radars.py
git commit -m "feat: add configurable radar definitions"
```

---

### Task 2: Presets and CLI Definition Commands

**Files:**
- Create: `src/alcove/radars/presets/tech-news.yml`
- Create: `src/alcove/radars/presets/world-news.yml`
- Modify: `src/alcove/radars/module.py`
- Modify: `src/alcove/cli.py`
- Test: `tests/test_radar_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_radar_cli.py`:

```python
from __future__ import annotations

from alcove.cli import main


def test_cli_radar_preset_list_and_init(tmp_path, capsys):
    home = tmp_path / ".alcove"

    list_code = main(["radar", "preset", "list", "--home", str(home), "--json"])
    list_output = capsys.readouterr()
    init_code = main(
        [
            "radar",
            "init",
            "tech-news",
            "--home",
            str(home),
            "--from-preset",
            "tech-news",
            "--json",
        ]
    )
    init_output = capsys.readouterr()
    radar_list_code = main(["radar", "list", "--home", str(home), "--json"])
    radar_list_output = capsys.readouterr()

    assert list_code == 0
    assert '"tech-news"' in list_output.out
    assert init_code == 0
    assert '"status": "saved"' in init_output.out
    assert radar_list_code == 0
    assert '"tech-news"' in radar_list_output.out
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_radar_cli.py -q --no-cov
```

Expected: CLI rejects unknown `radar` command.

- [ ] **Step 3: Add preset files**

Create `src/alcove/radars/presets/tech-news.yml`:

```yaml
schema: alcove/radar-definition/v1
id: tech-news
name: Tech News
status: active
schedule:
  enabled: false
  ttl_hours: 24
sources:
  - id: hackernews
    adapter: hackernews
    enabled: true
    limit: 30
  - id: github-trending
    adapter: github-trending
    enabled: true
    limit: 25
  - id: devto
    adapter: rss
    enabled: true
    limit: 20
    params:
      url: https://dev.to/feed
  - id: lobsters
    adapter: rss
    enabled: true
    limit: 20
    params:
      url: https://lobste.rs/rss
profile:
  languages: [en, zh]
  interest_tags: [LLM, AI, open source, productivity]
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
  enabled: false
  channel: telegram
tags: [preset, technology]
```

Create `src/alcove/radars/presets/world-news.yml`:

```yaml
schema: alcove/radar-definition/v1
id: world-news
name: World News
status: active
schedule:
  enabled: false
  ttl_hours: 24
sources:
  - id: google-news-en
    adapter: rss
    enabled: true
    limit: 20
    params:
      url: https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en
  - id: google-news-zh
    adapter: rss
    enabled: true
    limit: 20
    params:
      url: https://news.google.com/rss?hl=zh-CN&gl=CN&ceid=CN:zh-CN
  - id: bbc-world
    adapter: rss
    enabled: true
    limit: 20
    params:
      url: http://feeds.bbci.co.uk/news/world/rss.xml
  - id: cnn-world
    adapter: rss
    enabled: true
    limit: 20
    params:
      url: http://rss.cnn.com/rss/edition_world.rss
profile:
  languages: [en, zh]
  regions: [global, US, CN, EU]
  interest_tags: [technology, science, economy, politics]
  blocked_keywords: [sponsored, native ad, propaganda]
  min_score_threshold: 0.5
scoring:
  mode: hybrid
  ai_provider: claude
  ai_enabled_for_service: false
report:
  language: zh
  style: world-news-briefing
  formats: [md, html]
notify:
  enabled: false
  channel: telegram
tags: [preset, news]
```

- [ ] **Step 4: Add preset methods**

Append to `RadarModule`:

```python
    def preset_list(self) -> dict[str, Any]:
        presets = []
        for path in sorted(self._presets_root().glob("*.yml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict):
                presets.append(
                    {
                        "id": str(data.get("id") or path.stem),
                        "name": str(data.get("name") or path.stem),
                        "path": path.name,
                    }
                )
        return {"count": len(presets), "presets": presets}

    def init_from_preset(self, preset_id: str, radar_id: str = "") -> dict[str, Any]:
        preset_path = self._presets_root() / f"{normalize_slug(preset_id)}.yml"
        if not preset_path.is_file():
            raise FileNotFoundError(f"Radar preset not found: {preset_id}")
        data = yaml.safe_load(preset_path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Radar preset is invalid: {preset_id}")
        if radar_id:
            data["id"] = normalize_slug(radar_id)
        return self.upsert_definition(self._definition(data))

    def _presets_root(self) -> Path:
        return Path(__file__).resolve().parent / "presets"
```

- [ ] **Step 5: Add CLI parser and handler**

In `src/alcove/cli.py`, add a `radar` parser near other global commands:

```python
    radar = sub.add_parser("radar", help="Run configurable information radars")
    radar.add_argument("--home")
    radar_sub = radar.add_subparsers(dest="radar_command", required=True)
    radar_list = radar_sub.add_parser("list", help="List configured radar definitions")
    radar_list.add_argument("--home")
    radar_list.add_argument("--status", default="active")
    radar_list.add_argument("--json", action="store_true")
    radar_init = radar_sub.add_parser("init", help="Create a radar definition")
    radar_init.add_argument("--home")
    radar_init.add_argument("radar_id")
    radar_init.add_argument("--from-preset", default="")
    radar_init.add_argument("--json", action="store_true")
    radar_preset = radar_sub.add_parser("preset", help="Work with packaged radar presets")
    radar_preset.add_argument("--home")
    radar_preset_sub = radar_preset.add_subparsers(dest="radar_preset_command", required=True)
    radar_preset_list = radar_preset_sub.add_parser("list", help="List packaged radar presets")
    radar_preset_list.add_argument("--json", action="store_true")
```

In the command handling section:

```python
        if args.command == "radar":
            from alcove.radars import RadarModule

            radar_module = RadarModule(home)
            if args.radar_command == "list":
                payload = radar_module.list(status=args.status)
            elif args.radar_command == "init":
                if not args.from_preset:
                    parser.error("--from-preset is required for radar init in this release")
                payload = radar_module.init_from_preset(args.from_preset, args.radar_id)
            elif args.radar_command == "preset":
                if args.radar_preset_command == "list":
                    payload = radar_module.preset_list()
                else:
                    parser.error("the following arguments are required: radar_preset_command")
            else:
                parser.error("the following arguments are required: radar_command")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
```

- [ ] **Step 6: Run tests and commit**

Run:

```bash
uv run pytest tests/test_radars.py tests/test_radar_cli.py -q --no-cov
uv run mypy src/alcove/radars/models.py src/alcove/radars/module.py src/alcove/cli.py
```

Commit:

```bash
git add src/alcove/radars src/alcove/cli.py tests/test_radar_cli.py
git commit -m "feat: add radar presets and CLI definitions"
```

---

### Task 3: Source Adapter Registry and Deterministic Fetchers

**Files:**
- Create: `src/alcove/radars/sources/base.py`
- Create: `src/alcove/radars/sources/__init__.py`
- Create: `src/alcove/radars/sources/rss.py`
- Create: `src/alcove/radars/sources/fixture.py`
- Create: `src/alcove/radars/sources/generic_html.py`
- Test: `tests/test_radar_sources.py`

- [ ] **Step 1: Write failing adapter tests**

Create `tests/test_radar_sources.py`:

```python
from __future__ import annotations

from pathlib import Path

from alcove.radars.models import RadarDefinition, RadarSource
from alcove.radars.sources import fetch_source


def test_fixture_adapter_loads_items_from_json_file(tmp_path):
    fixture = tmp_path / "items.json"
    fixture.write_text(
        '[{"title":"Useful AI article","url":"https://example.com/ai","summary":"Good signal"}]',
        encoding="utf-8",
    )
    definition = RadarDefinition(
        id="custom",
        name="Custom",
        sources=[RadarSource(id="fixture", adapter="fixture", params={"path": str(fixture)})],
    )

    items = fetch_source(definition, definition.sources[0])

    assert len(items) == 1
    assert items[0].source_id == "fixture"
    assert items[0].title == "Useful AI article"


def test_rss_adapter_reads_local_feed(tmp_path):
    feed = tmp_path / "feed.xml"
    feed.write_text(
        """<?xml version="1.0"?>
<rss version="2.0"><channel>
<item><title>First News</title><link>https://example.com/first</link><description>Summary</description></item>
</channel></rss>""",
        encoding="utf-8",
    )
    definition = RadarDefinition(
        id="news",
        name="News",
        sources=[RadarSource(id="local-rss", adapter="rss", params={"url": feed.as_uri()})],
    )

    items = fetch_source(definition, definition.sources[0])

    assert items[0].title == "First News"
    assert items[0].url == "https://example.com/first"


def test_generic_html_adapter_extracts_link_pattern(tmp_path):
    page = tmp_path / "index.html"
    page.write_text(
        '<a href="https://example.com/blog/one">First blog post</a><a href="/about">About</a>',
        encoding="utf-8",
    )
    definition = RadarDefinition(
        id="html",
        name="HTML",
        sources=[
            RadarSource(
                id="html",
                adapter="generic-html",
                params={"url": page.as_uri(), "link_pattern": "/blog/"},
            )
        ],
    )

    items = fetch_source(definition, definition.sources[0])

    assert [item.url for item in items] == ["https://example.com/blog/one"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_radar_sources.py -q --no-cov
```

Expected: import failure for `alcove.radars.sources`.

- [ ] **Step 3: Implement source adapter interface and registry**

Create `src/alcove/radars/sources/base.py`:

```python
from __future__ import annotations

from typing import Protocol

from alcove.radars.models import RadarDefinition, RadarItem, RadarSource


class SourceAdapter(Protocol):
    adapter_id: str

    def fetch(self, definition: RadarDefinition, source: RadarSource) -> list[RadarItem]:
        ...
```

Create `src/alcove/radars/sources/__init__.py`:

```python
from __future__ import annotations

from alcove.radars.models import RadarDefinition, RadarItem, RadarSource
from alcove.radars.sources.fixture import FixtureAdapter
from alcove.radars.sources.generic_html import GenericHtmlAdapter
from alcove.radars.sources.rss import RssAdapter


_ADAPTERS = {
    "fixture": FixtureAdapter(),
    "generic-html": GenericHtmlAdapter(),
    "rss": RssAdapter(),
}


def fetch_source(definition: RadarDefinition, source: RadarSource) -> list[RadarItem]:
    adapter = _ADAPTERS.get(source.adapter)
    if adapter is None:
        raise ValueError(f"Unsupported radar source adapter: {source.adapter}")
    return adapter.fetch(definition, source)
```

- [ ] **Step 4: Implement fixture, RSS, and generic HTML adapters**

Create `src/alcove/radars/sources/fixture.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from alcove.radars.models import RadarDefinition, RadarItem, RadarSource


class FixtureAdapter:
    adapter_id = "fixture"

    def fetch(self, definition: RadarDefinition, source: RadarSource) -> list[RadarItem]:
        path = Path(str(source.params.get("path") or "")).expanduser()
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("Fixture radar source must be a JSON list")
        items = []
        for row in data[: source.limit or len(data)]:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "").strip()
            url = str(row.get("url") or "").strip()
            if title and url:
                items.append(
                    RadarItem(
                        source_id=source.id,
                        adapter=source.adapter,
                        title=title,
                        url=url,
                        summary=str(row.get("summary") or row.get("description") or ""),
                        tags=[str(tag) for tag in row.get("tags") or []],
                    )
                )
        return items
```

Create `src/alcove/radars/sources/rss.py`:

```python
from __future__ import annotations

from urllib.request import Request, urlopen
from xml.etree import ElementTree

from alcove.radars.models import RadarDefinition, RadarItem, RadarSource


class RssAdapter:
    adapter_id = "rss"

    def fetch(self, definition: RadarDefinition, source: RadarSource) -> list[RadarItem]:
        url = str(source.params.get("url") or "")
        if not url:
            raise ValueError(f"RSS radar source requires params.url: {source.id}")
        request = Request(url, headers={"User-Agent": "AlcoveRadar/0.1"})  # noqa: S310
        with urlopen(request, timeout=20) as response:  # noqa: S310
            raw = response.read(2_000_000)
        root = ElementTree.fromstring(raw)
        nodes = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
        items = []
        for node in nodes[: source.limit]:
            title = _first_text(node, ["title", "{http://www.w3.org/2005/Atom}title"])
            link = _first_text(node, ["link"])
            atom_link = node.find("{http://www.w3.org/2005/Atom}link")
            if not link and atom_link is not None:
                link = str(atom_link.attrib.get("href") or "")
            summary = _first_text(node, ["description", "summary", "{http://www.w3.org/2005/Atom}summary"])
            if title and link:
                items.append(
                    RadarItem(
                        source_id=source.id,
                        adapter=source.adapter,
                        title=title,
                        url=link,
                        summary=summary,
                    )
                )
        return items


def _first_text(node: ElementTree.Element, names: list[str]) -> str:
    for name in names:
        child = node.find(name)
        if child is not None and child.text:
            return child.text.strip()
    return ""
```

Create `src/alcove/radars/sources/generic_html.py`:

```python
from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from alcove.radars.models import RadarDefinition, RadarItem, RadarSource


class GenericHtmlAdapter:
    adapter_id = "generic-html"

    def fetch(self, definition: RadarDefinition, source: RadarSource) -> list[RadarItem]:
        url = str(source.params.get("url") or "")
        pattern = str(source.params.get("link_pattern") or "")
        if not url:
            raise ValueError(f"HTML radar source requires params.url: {source.id}")
        request = Request(url, headers={"User-Agent": "AlcoveRadar/0.1"})  # noqa: S310
        with urlopen(request, timeout=20) as response:  # noqa: S310
            html = response.read(2_000_000).decode("utf-8", errors="replace")
        parser = _AnchorParser(base_url=url)
        parser.feed(html)
        rows = []
        seen: set[str] = set()
        for href, text in parser.links:
            if pattern and pattern not in href:
                continue
            if href in seen:
                continue
            title = text.strip()
            if len(title) < 4:
                continue
            seen.add(href)
            rows.append(RadarItem(source_id=source.id, adapter=source.adapter, title=title, url=href))
            if source.limit and len(rows) >= source.limit:
                break
        return rows


class _AnchorParser(HTMLParser):
    def __init__(self, *, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.current_href = ""
        self.current_text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attrs_dict = dict(attrs)
        href = attrs_dict.get("href") or ""
        if href:
            self.current_href = urljoin(self.base_url, href)
            self.current_text = []

    def handle_data(self, data: str) -> None:
        if self.current_href:
            self.current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.current_href:
            self.links.append((self.current_href, " ".join(self.current_text).strip()))
            self.current_href = ""
            self.current_text = []
```

- [ ] **Step 5: Run tests and commit**

Run:

```bash
uv run pytest tests/test_radar_sources.py -q --no-cov
uv run mypy src/alcove/radars/sources/base.py src/alcove/radars/sources/__init__.py src/alcove/radars/sources/rss.py src/alcove/radars/sources/generic_html.py src/alcove/radars/sources/fixture.py
```

Commit:

```bash
git add src/alcove/radars/sources tests/test_radar_sources.py
git commit -m "feat: add radar source adapters"
```

---

### Task 4: Pipeline, Rule Scoring, Reports, and `radar run`

**Files:**
- Create: `src/alcove/radars/scoring.py`
- Create: `src/alcove/radars/reporting.py`
- Create: `src/alcove/radars/pipeline.py`
- Modify: `src/alcove/radars/module.py`
- Modify: `src/alcove/cli.py`
- Test: `tests/test_radars.py`
- Test: `tests/test_radar_cli.py`

- [ ] **Step 1: Write failing pipeline tests**

Append to `tests/test_radars.py`:

```python
import json


def test_radar_run_fetches_scores_reports_and_writes_cache(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    fixture = tmp_path / "items.json"
    fixture.write_text(
        json.dumps(
            [
                {"title": "LLM open source release", "url": "https://example.com/llm"},
                {"title": "Sponsored gambling ad", "url": "https://example.com/ad"},
            ]
        ),
        encoding="utf-8",
    )
    module = RadarModule(home)
    module.upsert_definition(
        RadarDefinition(
            id="tech-news",
            name="Tech News",
            sources=[RadarSource(id="fixture", adapter="fixture", params={"path": str(fixture)})],
            profile={
                "interest_tags": ["LLM", "open source"],
                "blocked_keywords": ["gambling"],
                "min_score_threshold": 0.5,
            },
            report={"formats": ["md", "html"], "language": "zh"},
        )
    )

    result = module.run("tech-news", today="2026-07-12")

    assert result["status"] == "completed"
    assert result["fetched"] == 2
    assert result["included"] == 1
    assert (home.root / "radars/cache/tech-news/2026-07-12/scored.json").is_file()
    assert (home.root / "radars/reports/tech-news/2026-07-12.md").is_file()
    assert (home.root / "radars/reports/tech-news/2026-07-12.html").is_file()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_radars.py::test_radar_run_fetches_scores_reports_and_writes_cache -q --no-cov
```

Expected: `RadarModule` has no `run`.

- [ ] **Step 3: Implement scoring**

Create `src/alcove/radars/scoring.py`:

```python
from __future__ import annotations

from alcove.radars.models import RadarDefinition, RadarItem


def score_items(definition: RadarDefinition, items: list[RadarItem]) -> list[RadarItem]:
    profile = definition.profile
    blocked = [str(value).lower() for value in profile.get("blocked_keywords") or []]
    interests = [str(value).lower() for value in profile.get("interest_tags") or []]
    threshold = float(profile.get("min_score_threshold") or 0.5)
    scored = []
    for item in items:
        text = " ".join([item.title, item.summary, " ".join(item.tags)]).lower()
        if any(keyword and keyword in text for keyword in blocked):
            scored.append(_replace_score(item, score=0.0, reason="blocked keyword", included=False))
            continue
        matches = [tag for tag in interests if tag and tag in text]
        score = min(1.0, 0.35 + 0.2 * len(matches))
        reason = "matched: " + ", ".join(matches[:5]) if matches else "baseline source signal"
        scored.append(_replace_score(item, score=score, reason=reason, included=score >= threshold))
    return scored


def _replace_score(item: RadarItem, *, score: float, reason: str, included: bool) -> RadarItem:
    return RadarItem(
        source_id=item.source_id,
        adapter=item.adapter,
        title=item.title,
        url=item.url,
        summary=item.summary,
        author=item.author,
        published_at=item.published_at,
        tags=item.tags,
        metrics=item.metrics,
        score=score,
        score_reason=reason,
        included=included,
    )
```

- [ ] **Step 4: Implement reporting**

Create `src/alcove/radars/reporting.py`:

```python
from __future__ import annotations

from html import escape

from alcove.radars.models import RadarDefinition, RadarItem


def render_markdown(definition: RadarDefinition, items: list[RadarItem], *, today: str) -> str:
    included = [item for item in items if item.included]
    lines = [
        f"# {definition.name} - {today}",
        "",
        f"- Total items: {len(items)}",
        f"- Included items: {len(included)}",
        "",
        "## Top Items",
        "",
    ]
    for item in sorted(included, key=lambda row: row.score, reverse=True):
        lines.append(f"- [{item.title}]({item.url}) - {item.score:.2f} - {item.score_reason}")
        if item.summary:
            lines.append(f"  - {item.summary}")
    if not included:
        lines.append("- No items passed the threshold.")
    return "\n".join(lines) + "\n"


def render_html(definition: RadarDefinition, items: list[RadarItem], *, today: str) -> str:
    body = "\n".join(
        f'<li><a href="{escape(item.url)}">{escape(item.title)}</a> '
        f'<span>{item.score:.2f}</span><p>{escape(item.summary or item.score_reason)}</p></li>'
        for item in sorted([row for row in items if row.included], key=lambda row: row.score, reverse=True)
    )
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{escape(definition.name)} - {today}</title></head>
<body><main><h1>{escape(definition.name)}</h1><p>{today}</p><ul>{body}</ul></main></body>
</html>
"""
```

- [ ] **Step 5: Implement pipeline and module run**

Create `src/alcove/radars/pipeline.py`:

```python
from __future__ import annotations

from datetime import date
import json
from typing import Any

from alcove.paths import compact_user_path
from alcove.radars.models import RadarDefinition, RadarItem, RADAR_RUN_SCHEMA, now_iso
from alcove.radars.reporting import render_html, render_markdown
from alcove.radars.scoring import score_items
from alcove.radars.sources import fetch_source


class RadarPipeline:
    def __init__(self, module: Any) -> None:
        self.module = module

    def run(self, definition: RadarDefinition, *, today: str | None = None, skip_fetch: bool = False) -> dict[str, Any]:
        run_day = today or date.today().isoformat()
        cache_dir = self.module.cache_root / definition.id / run_day
        report_dir = self.module.reports_root / definition.id
        raw_path = cache_dir / "raw.json"
        if skip_fetch and raw_path.is_file():
            raw_items = _items_from_json(json.loads(raw_path.read_text(encoding="utf-8")))
        else:
            raw_items = self._fetch(definition)
            cache_dir.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(json.dumps([item.as_dict() for item in raw_items], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        scored = score_items(definition, _dedupe(raw_items))
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "scored.json").write_text(json.dumps([item.as_dict() for item in scored], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report_dir.mkdir(parents=True, exist_ok=True)
        md_path = report_dir / f"{run_day}.md"
        html_path = report_dir / f"{run_day}.html"
        md_path.write_text(render_markdown(definition, scored, today=run_day), encoding="utf-8")
        html_path.write_text(render_html(definition, scored, today=run_day), encoding="utf-8")
        run_payload = {
            "schema": RADAR_RUN_SCHEMA,
            "id": definition.id,
            "status": "completed",
            "date": run_day,
            "run_at": now_iso(),
            "fetched": len(raw_items),
            "scored": len(scored),
            "included": len([item for item in scored if item.included]),
            "reports": {"md": compact_user_path(md_path), "html": compact_user_path(html_path)},
        }
        run_dir = self.module.runs_root / definition.id / run_day
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run.json").write_text(json.dumps(run_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return run_payload

    def _fetch(self, definition: RadarDefinition) -> list[RadarItem]:
        items: list[RadarItem] = []
        for source in definition.sources:
            if source.enabled:
                items.extend(fetch_source(definition, source))
        return items


def _dedupe(items: list[RadarItem]) -> list[RadarItem]:
    seen: set[str] = set()
    deduped = []
    for item in items:
        key = item.url or f"{item.source_id}:{item.title.lower()}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _items_from_json(rows: list[dict[str, Any]]) -> list[RadarItem]:
    return [
        RadarItem(
            source_id=str(row.get("source_id") or ""),
            adapter=str(row.get("adapter") or ""),
            title=str(row.get("title") or ""),
            url=str(row.get("url") or ""),
            summary=str(row.get("summary") or ""),
            tags=[str(tag) for tag in row.get("tags") or []],
        )
        for row in rows
        if isinstance(row, dict)
    ]
```

Add to `RadarModule`:

```python
    def run(self, radar_id: str, *, today: str | None = None, skip_fetch: bool = False) -> dict[str, Any]:
        from alcove.radars.pipeline import RadarPipeline

        return RadarPipeline(self).run(self.get(radar_id), today=today, skip_fetch=skip_fetch)
```

- [ ] **Step 6: Add CLI run**

Add parser:

```python
    radar_run = radar_sub.add_parser("run", help="Run a radar definition")
    radar_run.add_argument("--home")
    radar_run.add_argument("radar_id")
    radar_run.add_argument("--skip-fetch", action="store_true")
    radar_run.add_argument("--json", action="store_true")
```

Add handler branch:

```python
            elif args.radar_command == "run":
                payload = radar_module.run(args.radar_id, skip_fetch=args.skip_fetch)
```

- [ ] **Step 7: Run tests and commit**

Run:

```bash
uv run pytest tests/test_radars.py tests/test_radar_cli.py tests/test_radar_sources.py -q --no-cov
uv run mypy src/alcove/radars
```

Commit:

```bash
git add src/alcove/radars src/alcove/cli.py tests/test_radars.py tests/test_radar_cli.py
git commit -m "feat: run configurable radar reports"
```

---

### Task 5: Real Source Adapters from Social Radar

**Files:**
- Create: `src/alcove/radars/sources/hackernews.py`
- Create: `src/alcove/radars/sources/github_trending.py`
- Create: `src/alcove/radars/sources/reddit.py`
- Create: `src/alcove/radars/sources/finance.py`
- Modify: `src/alcove/radars/sources/__init__.py`
- Test: `tests/test_radar_sources.py`

- [ ] **Step 1: Add adapter fixture tests**

Append tests that use local fixture files instead of network:

```python
def test_hackernews_adapter_parses_local_topstories_fixture(tmp_path):
    stories = tmp_path / "stories.json"
    stories.write_text('[{"title":"AI story","url":"https://example.com/ai","score":42}]', encoding="utf-8")
    definition = RadarDefinition(
        id="tech",
        name="Tech",
        sources=[RadarSource(id="hn", adapter="hackernews", params={"fixture_path": str(stories)})],
    )

    items = fetch_source(definition, definition.sources[0])

    assert items[0].title == "AI story"
    assert items[0].metrics["score"] == 42


def test_reddit_adapter_parses_local_listing_fixture(tmp_path):
    listing = tmp_path / "reddit.json"
    listing.write_text(
        '{"data":{"children":[{"data":{"title":"World news","url":"https://example.com/news","subreddit":"worldnews","score":12}}]}}',
        encoding="utf-8",
    )
    definition = RadarDefinition(
        id="news",
        name="News",
        sources=[RadarSource(id="reddit", adapter="reddit", params={"fixture_path": str(listing), "subreddits": ["worldnews"]})],
    )

    items = fetch_source(definition, definition.sources[0])

    assert items[0].source_id == "reddit"
    assert "reddit:worldnews" in items[0].tags
```

- [ ] **Step 2: Implement adapters with fixture-first logic**

Implementation details:

- `hackernews.py`: use `params.fixture_path` when present; otherwise fetch Firebase top stories with per-item requests and limit.
- `github_trending.py`: parse GitHub Trending HTML using `HTMLParser`; use `params.fixture_path` when present.
- `reddit.py`: use public JSON listing URLs such as `https://www.reddit.com/r/<subreddit>/hot.json?limit=<n>` with a User-Agent; use `params.fixture_path` when present.
- `finance.py`: implement minimal fixture-compatible `finance-json` adapter first; defer fragile Yahoo/Finviz scraping unless local tests are stable.

The public registry should add:

```python
from alcove.radars.sources.github_trending import GitHubTrendingAdapter
from alcove.radars.sources.hackernews import HackerNewsAdapter
from alcove.radars.sources.reddit import RedditAdapter
from alcove.radars.sources.finance import FinanceJsonAdapter

_ADAPTERS.update(
    {
        "github-trending": GitHubTrendingAdapter(),
        "hackernews": HackerNewsAdapter(),
        "reddit": RedditAdapter(),
        "finance-json": FinanceJsonAdapter(),
    }
)
```

- [ ] **Step 3: Run adapter tests**

Run:

```bash
uv run pytest tests/test_radar_sources.py -q --no-cov
uv run mypy src/alcove/radars/sources
```

Expected: all fixture tests pass without network.

- [ ] **Step 4: Commit**

```bash
git add src/alcove/radars/sources tests/test_radar_sources.py
git commit -m "feat: add radar web source adapters"
```

---

### Task 6: Service Tick, Dashboard, and Search Integration

**Files:**
- Modify: `src/alcove/service.py`
- Modify: `src/alcove/dashboard.py`
- Modify: `src/alcove/search_global.py` or `src/alcove/search_sources.py`
- Test: `tests/test_radar_service.py`
- Test: `tests/test_radar_dashboard.py`

- [ ] **Step 1: Write failing service/dashboard tests**

Create `tests/test_radar_service.py`:

```python
from __future__ import annotations

import json

from alcove.home import AlcoveHome
from alcove.radars import RadarDefinition, RadarModule, RadarSchedule, RadarSource
from alcove.service import ServiceModule


def test_service_tick_runs_enabled_stale_radars(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    fixture = tmp_path / "items.json"
    fixture.write_text('[{"title":"AI signal","url":"https://example.com/ai"}]', encoding="utf-8")
    RadarModule(home).upsert_definition(
        RadarDefinition(
            id="custom",
            name="Custom",
            schedule=RadarSchedule(enabled=True, ttl_hours=1),
            sources=[RadarSource(id="fixture", adapter="fixture", params={"path": str(fixture)})],
        )
    )

    result = ServiceModule(home).tick(refresh_connectors=False, check_watchers=False, check_blogs=False)

    assert result["radars"]["status"] == "checked"
    assert result["radars"]["ran"] == 1
```

Create `tests/test_radar_dashboard.py`:

```python
from __future__ import annotations

from alcove.dashboard import DashboardModule
from alcove.home import AlcoveHome
from alcove.radars import RadarDefinition, RadarModule, RadarSource


def test_dashboard_snapshot_lists_generic_radars(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    RadarModule(home).upsert_definition(
        RadarDefinition(
            id="sports-news",
            name="Sports News",
            sources=[RadarSource(id="fixture", adapter="fixture", params={"path": str(tmp_path / "missing.json")})],
        )
    )

    snapshot = DashboardModule(home).snapshot()

    assert snapshot["summary"]["counts"]["radars"] == 1
    assert snapshot["radars"][0]["id"] == "sports-news"
    assert any(row["type"] == "radar" and row["title"] == "Sports News" for row in snapshot["search_index"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_radar_service.py tests/test_radar_dashboard.py -q --no-cov
```

Expected: missing `radars` payload.

- [ ] **Step 3: Add stale-run status to RadarModule**

Add:

```python
    def check_stale(self, *, now: str | None = None) -> dict[str, Any]:
        ran = 0
        skipped = 0
        errors = 0
        rows = []
        for definition in self._load_definitions():
            if definition.status != "active" or not definition.schedule.enabled:
                continue
            try:
                report = self.run(definition.id)
                rows.append({"id": definition.id, "status": "ran", "included": report.get("included", 0)})
                ran += 1
            except Exception as exc:
                rows.append({"id": definition.id, "status": "error", "error": str(exc)})
                errors += 1
        return {"status": "checked", "ran": ran, "skipped": skipped, "errors": errors, "radars": rows}

    def dashboard_rows(self) -> list[dict[str, Any]]:
        rows = []
        for definition in self._load_definitions():
            rows.append(
                {
                    "id": definition.id,
                    "name": definition.name,
                    "status": definition.status,
                    "schedule_enabled": definition.schedule.enabled,
                    "source_count": len(definition.sources),
                    "tags": definition.tags,
                }
            )
        return rows
```

- [ ] **Step 4: Wire service tick**

In `ServiceModule.tick`, add `check_radars: bool = True`, call:

```python
        radars_payload = (
            RadarModule(self.home).check_stale()
            if check_radars
            else {"status": "skipped", "ran": 0}
        )
```

Include in return and usage metrics:

```python
            "radars": radars_payload,
```

- [ ] **Step 5: Wire dashboard snapshot**

In `DashboardModule.snapshot`, include:

```python
        radar_rows = RadarModule(self.home).dashboard_rows()
```

Add counts:

```python
            "radars": len(radar_rows),
```

Add top-level:

```python
            "radars": radar_rows,
```

Add search rows:

```python
        for radar in snapshot.get("radars", []):
            rows.append(
                {
                    "type": "radar",
                    "title": str(radar.get("name") or radar.get("id") or ""),
                    "text": " ".join([str(radar.get("id") or ""), str(radar.get("status") or "")]),
                    "href": "/library",
                }
            )
```

- [ ] **Step 6: Run tests and commit**

Run:

```bash
uv run pytest tests/test_radar_service.py tests/test_radar_dashboard.py tests/test_service.py tests/test_dashboard.py -q --no-cov
uv run mypy src/alcove/radars src/alcove/service.py src/alcove/dashboard.py
```

Commit:

```bash
git add src/alcove/radars src/alcove/service.py src/alcove/dashboard.py tests/test_radar_service.py tests/test_radar_dashboard.py tests/test_service.py tests/test_dashboard.py
git commit -m "feat: integrate radars with service and dashboard"
```

---

### Task 7: Social Radar Migration

**Files:**
- Create: `src/alcove/radars/migration.py`
- Modify: `src/alcove/radars/module.py`
- Modify: `src/alcove/cli.py`
- Test: `tests/test_radar_migration.py`

- [ ] **Step 1: Write failing migration test**

Create `tests/test_radar_migration.py`:

```python
from __future__ import annotations

import json

from alcove.cli import main


def test_import_social_radar_creates_user_definitions_and_copies_history(tmp_path, capsys):
    social = tmp_path / ".social_radar"
    (social / "config").mkdir(parents=True)
    (social / "data/radar").mkdir(parents=True)
    (social / "reports").mkdir(parents=True)
    (social / "config/preference_profile.json").write_text(
        json.dumps({"interest_tags": ["LLM"], "blocked_keywords": ["ad"], "min_score_threshold": 0.6}),
        encoding="utf-8",
    )
    (social / "data/radar/all_2026-07-11.json").write_text(
        json.dumps({"items": [{"title": "LLM", "url": "https://example.com"}]}),
        encoding="utf-8",
    )
    (social / "reports/2026-07-11.html").write_text("<html>report</html>", encoding="utf-8")
    home = tmp_path / ".alcove"

    code = main(["radar", "import-social-radar", str(social), "--home", str(home), "--json"])
    output = capsys.readouterr()

    assert code == 0
    assert '"tech-news"' in output.out
    assert (home / "radars/definitions/tech-news.yml").is_file()
    assert (home / "radars/cache/tech-news/2026-07-11/scored.json").is_file()
    assert (home / "radars/reports/tech-news/2026-07-11.html").is_file()
```

- [ ] **Step 2: Implement migration**

Create `src/alcove/radars/migration.py`:

```python
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from alcove.radars.models import RadarDefinition, RadarSource


def import_social_radar(module: Any, source_home: str) -> dict[str, Any]:
    root = Path(source_home).expanduser()
    if not root.is_dir():
        raise FileNotFoundError(f"social-radar home not found: {source_home}")
    imported = []
    mappings = [
        ("tech-news", root / "config/preference_profile.json", root / "data/radar", root / "reports"),
        ("world-news", root / "config/news_preference_profile.json", root / "data/news_radar", root / "reports/news"),
        ("stocks", root / "config/stock_preference_profile.json", root / "data/stock_radar", root / "reports/stock"),
    ]
    for radar_id, profile_path, data_dir, reports_dir in mappings:
        if not profile_path.is_file():
            continue
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        module.upsert_definition(
            RadarDefinition(
                id=radar_id,
                name=_display_name(radar_id),
                sources=[RadarSource(id="legacy-cache", adapter="fixture", enabled=False)],
                profile=profile if isinstance(profile, dict) else {},
                report={"formats": ["md", "html"], "language": "zh"},
                tags=["imported", "social-radar"],
            )
        )
        copied_cache = _copy_cache(module, radar_id, data_dir)
        copied_reports = _copy_reports(module, radar_id, reports_dir)
        imported.append({"id": radar_id, "cache_files": copied_cache, "report_files": copied_reports})
    return {"status": "imported", "source": str(root), "imported": imported}


def _display_name(radar_id: str) -> str:
    return radar_id.replace("-", " ").title()


def _copy_cache(module: Any, radar_id: str, data_dir: Path) -> int:
    if not data_dir.is_dir():
        return 0
    copied = 0
    for path in sorted(data_dir.glob("all_*.json")):
        day = path.stem.removeprefix("all_")
        target = module.cache_root / radar_id / day / "scored.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        copied += 1
    return copied


def _copy_reports(module: Any, radar_id: str, reports_dir: Path) -> int:
    if not reports_dir.is_dir():
        return 0
    copied = 0
    target_dir = module.reports_root / radar_id
    target_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(reports_dir.glob("*.*")):
        if path.suffix not in {".md", ".html"}:
            continue
        shutil.copyfile(path, target_dir / path.name)
        copied += 1
    return copied
```

Add to `RadarModule`:

```python
    def import_social_radar(self, source_home: str) -> dict[str, Any]:
        from alcove.radars.migration import import_social_radar

        return import_social_radar(self, source_home)
```

Add CLI parser:

```python
    radar_import = radar_sub.add_parser("import-social-radar", help="Import old social-radar data")
    radar_import.add_argument("--home")
    radar_import.add_argument("source_home")
    radar_import.add_argument("--json", action="store_true")
```

Add handler:

```python
            elif args.radar_command == "import-social-radar":
                payload = radar_module.import_social_radar(args.source_home)
```

- [ ] **Step 3: Run tests and commit**

Run:

```bash
uv run pytest tests/test_radar_migration.py tests/test_radar_cli.py -q --no-cov
uv run mypy src/alcove/radars/migration.py src/alcove/radars/module.py src/alcove/cli.py
```

Commit:

```bash
git add src/alcove/radars/migration.py src/alcove/radars/module.py src/alcove/cli.py tests/test_radar_migration.py
git commit -m "feat: import social radar definitions"
```

---

### Task 8: Hub Skill, Docs, and AI Eval

**Files:**
- Modify: `src/alcove/profile_templates/hub/skills/alcove-hub/SKILL.md`
- Modify: `src/alcove/ai_eval.py`
- Modify: `pyproject.toml`
- Modify: `docs/modules.md`
- Modify: `docs/entry-modes.md`
- Modify: `docs/usage.md`
- Modify: `README.md`
- Test: `tests/test_ai_eval.py`
- Test: `tests/test_entry_profiles.py`

- [ ] **Step 1: Update hub routing text**

In `alcove-hub/SKILL.md`, add routing:

```markdown
- radar / daily briefing / 技术雷达 / 新闻雷达 / 股票雷达 / 体育资讯:
  use `alcove radar list --json`, then `alcove radar run <radar-id> --json`.
  Treat radar IDs as user data from `~/.alcove/radars/definitions/`; do not assume
  tech/news/stock are the only valid categories.
```

Add commands:

```sh
alcove radar list --json
alcove radar preset list --json
alcove radar init tech-news --from-preset tech-news --json
alcove radar run tech-news --json
alcove radar import-social-radar ~/.social_radar --json
```

- [ ] **Step 2: Add AI eval evidence**

In `src/alcove/ai_eval.py`, add a `radars` section to the packet builder with:

```python
        "radars": {
            "requirements": [
                "Radar categories are user-defined definitions, not hard-coded modules.",
                "Built-in tech-news and world-news are presets only.",
                "stocks and sports-news can exist as user-owned definitions.",
                "Radar reports are time-sensitive signals, not durable OKF notes.",
            ],
        },
```

Update test expectations in `tests/test_ai_eval.py` to assert `"radars"` appears.

- [ ] **Step 3: Add radars to strict mypy files**

In `pyproject.toml`, add the radar package files to `[tool.mypy].files`:

```toml
    "src/alcove/radars/models.py",
    "src/alcove/radars/module.py",
    "src/alcove/radars/pipeline.py",
    "src/alcove/radars/reporting.py",
    "src/alcove/radars/scoring.py",
    "src/alcove/radars/migration.py",
    "src/alcove/radars/sources/base.py",
    "src/alcove/radars/sources/__init__.py",
    "src/alcove/radars/sources/rss.py",
    "src/alcove/radars/sources/fixture.py",
    "src/alcove/radars/sources/generic_html.py",
    "src/alcove/radars/sources/hackernews.py",
    "src/alcove/radars/sources/github_trending.py",
    "src/alcove/radars/sources/reddit.py",
    "src/alcove/radars/sources/finance.py",
```

- [ ] **Step 4: Update docs**

Add concise docs:

```markdown
## Radars

Radars are user-configurable daily information briefings. Alcove ships source
adapters and optional presets, but radar categories are user data under
`~/.alcove/radars/definitions/`.

```sh
alcove radar preset list
alcove radar init tech-news --from-preset tech-news
alcove radar run tech-news --json
alcove radar import-social-radar ~/.social_radar --json
```
```

Document that `tech-news` and `world-news` are packaged presets, while `stocks`
and `sports-news` are examples of user-owned definitions.

- [ ] **Step 5: Run tests and commit**

Run:

```bash
uv run pytest tests/test_ai_eval.py tests/test_entry_profiles.py -q --no-cov
uv run mypy
```

Commit:

```bash
git add src/alcove/profile_templates/hub/skills/alcove-hub/SKILL.md src/alcove/ai_eval.py pyproject.toml docs README.md tests/test_ai_eval.py tests/test_entry_profiles.py
git commit -m "docs: document configurable radar workflows"
```

---

### Task 9: Local Migration and Real Smoke

**Files:**
- No new source files unless previous tasks reveal bugs.
- Local data: `~/.alcove/radars/**`

- [ ] **Step 1: Install latest editable CLI**

Run:

```bash
uv tool install --force -e .
```

Expected: global `alcove` resolves to this checkout.

- [ ] **Step 2: Import local social-radar data**

Run:

```bash
alcove radar import-social-radar ~/.social_radar --home ~/.alcove --json
```

Expected:

```text
status imported
imported includes tech-news, world-news, stocks if matching old config exists
```

- [ ] **Step 3: Initialize sports-news as user-owned example**

Create a small local definition:

```bash
cat > /tmp/alcove-sports-items.json <<'JSON'
[
  {"title": "NBA finals tactical analysis", "url": "https://example.com/nba", "summary": "Fixture item for sports radar smoke.", "tags": ["NBA"]}
]
JSON
```

Use CLI or direct YAML write through `RadarModule` in a Python one-liner:

```bash
uv run python - <<'PY'
from alcove.home import AlcoveHome
from alcove.radars import RadarDefinition, RadarModule, RadarSource
home = AlcoveHome.init("~/.alcove")
RadarModule(home).upsert_definition(RadarDefinition(
    id="sports-news",
    name="Sports News",
    sources=[RadarSource(id="fixture", adapter="fixture", params={"path": "/tmp/alcove-sports-items.json"})],
    profile={"interest_tags": ["NBA"], "blocked_keywords": ["betting"], "min_score_threshold": 0.5},
    report={"formats": ["md", "html"], "language": "zh"},
))
PY
```

- [ ] **Step 4: Run deterministic local smoke**

Run:

```bash
alcove radar list --home ~/.alcove --json
alcove radar run sports-news --home ~/.alcove --json
alcove service tick --home ~/.alcove --skip-connectors --skip-watchers --skip-blogs --json
alcove dashboard --home ~/.alcove build --json
```

Expected:

- `sports-news` appears in `radar list`.
- `sports-news` writes `~/.alcove/radars/reports/sports-news/<date>.md`.
- `service tick` includes a `radars` payload.
- Dashboard snapshot includes `summary.counts.radars`.

- [ ] **Step 5: Run full checks**

Run:

```bash
uv run ruff format src tests
uv run ruff check src tests
uv run mypy
uv run pytest
scripts/check.sh
```

Expected: all pass.

- [ ] **Step 6: Commit final integration fixes**

If smoke reveals fixes:

```bash
git add <fixed-files>
git commit -m "fix: harden configurable radar smoke"
```

If no fixes are needed, do not create an empty commit.

---

## Self-Review

Spec coverage:

- Generic radar definitions: Tasks 1-2.
- Packaged presets: Task 2.
- Source adapters: Tasks 3 and 5.
- Pipeline, scoring, report cache: Task 4.
- Service/dashboard/search: Task 6.
- Social-radar migration: Task 7.
- Hub docs and AI eval: Task 8.
- Local machine verification: Task 9.

Known intentional limits:

- Playwright-only trend sources are not enabled by default. They can be added later as adapters once fixture and launchd behavior are stable.
- `stocks` is imported as user data and can run through fixture/cache first. Fragile live finance scraping should be added adapter-by-adapter with tests, not as a hard-coded stock module.
- AI scoring is represented in configuration and eval guidance, but deterministic service runs do not depend on Claude by default.

No placeholder sections remain. Type names are consistent with the planned public interface: `RadarModule`, `RadarDefinition`, `RadarSource`, `RadarItem`, and `RadarPipeline`.
