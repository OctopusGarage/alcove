<a id="readme-top"></a>

# Alcove

[![CI](https://github.com/OctopusGarage/alcove/actions/workflows/ci.yml/badge.svg)](https://github.com/OctopusGarage/alcove/actions/workflows/ci.yml)
[![Gitleaks](https://github.com/OctopusGarage/alcove/actions/workflows/gitleaks.yml/badge.svg)](https://github.com/OctopusGarage/alcove/actions/workflows/gitleaks.yml)
[![Project Health](https://github.com/OctopusGarage/alcove/actions/workflows/project-health.yml/badge.svg)](https://github.com/OctopusGarage/alcove/actions/workflows/project-health.yml)
[![Coverage](https://codecov.io/gh/OctopusGarage/alcove/branch/main/graph/badge.svg)](https://codecov.io/gh/OctopusGarage/alcove)
[![Pages](https://github.com/OctopusGarage/alcove/actions/workflows/pages.yml/badge.svg)](https://octopusgarage.github.io/alcove/)
[![version](https://img.shields.io/badge/version-0.1.0-blue)](pyproject.toml)
[![Python](https://img.shields.io/badge/python-%3E%3D3.12-brightgreen)](https://www.python.org/)
[![uv](https://img.shields.io/badge/managed_with-uv-654FF0)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/badge/lint-Ruff-261230)](https://docs.astral.sh/ruff/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

<p align="center">
  A local-first personal intelligence hub for managed knowledge bases, global memory,
  external indexes, scheduled radars, dashboard views, and AI-agent entry workflows.
  <br />
  <br />
  <a href="docs/usage.md"><strong>Read the usage guide »</strong></a>
  <br />
  <br />
  <a href="https://octopusgarage.github.io/alcove/">Website</a>
  ·
  <a href="docs/architecture.md">Architecture</a>
  ·
  <a href="docs/README.md">Documentation</a>
  ·
  <a href="https://github.com/OctopusGarage/alcove/issues/new?template=bug_report.yml">Report Bug</a>
  ·
  <a href="https://github.com/OctopusGarage/alcove/issues/new?template=feature_request.yml">Request Feature</a>
</p>

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#about-the-project">About The Project</a></li>
    <li><a href="#features">Features</a></li>
    <li><a href="#architecture">Architecture</a></li>
    <li><a href="#getting-started">Getting Started</a></li>
    <li><a href="#core-workflows">Core Workflows</a></li>
    <li><a href="#operations">Operations</a></li>
    <li><a href="#documentation">Documentation</a></li>
    <li><a href="#development">Development</a></li>
    <li><a href="#license">License</a></li>
  </ol>
</details>

## About The Project

Alcove keeps personal knowledge work inspectable, portable, and agent-friendly.
It stores user data in local Markdown, YAML, and JSON, while providing governed
CLI/MCP write paths and broad AI-led read paths.

The core model:

```text
Read  -> search candidates, inspect local evidence, synthesize with context
Write -> route through Alcove CLI/MCP contracts, update indexes, validate
```

Data ownership is explicit:

- `~/.alcove` stores global memory, indexes, service state, dashboard snapshots,
  radars, publishers, automations, and usage rollups.
- Managed knowledge bases live wherever the user chooses and are registered
  under `~/.alcove/knowledge-bases/`.
- Mounts and connectors index external sources without taking ownership of the
  original data.
- The dashboard and Apple Notes publisher are derived views, not source-of-truth
  stores.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Features

- **Managed knowledge bases** — inbox capture, manual drafts, archive, OKF notes,
  taxonomy, validation, and indexed retrieval.
- **Global personal memory** — pins, prompts, tasks, ideas, routines, and local
  project aliases under Alcove Home.
- **External knowledge sources** — read-only mounts plus Apple Notes, GitHub
  Stars, and Chrome Bookmarks connectors.
- **Agent entry modes** — Hub workspace, lightweight global MCP, managed-KB
  workspace, and local service runtime.
- **Configurable radars and monitors** — scheduled information reports, watched
  feeds/pages, blog discovery, optional capture, optional AI summary, and
  Telegram/Feishu/tmux-claude-bot notification sinks.
- **Local dashboard** — browser-facing workbench generated from local data.
- **External readable mirrors** — Apple Notes publishing for selected personal
  memory views.
- **Health and repair** — cross-module data checks, OKF validation, safe index
  rebuilds, deep local maintenance, and agent smoke/eval hooks.

### Built With

- **Language / runtime** — Python 3.12+
- **Packaging / environment** — [uv](https://docs.astral.sh/uv/)
- **CLI / MCP** — argparse, [FastMCP](https://github.com/jlowin/fastmcp)
- **Data formats** — Markdown + YAML frontmatter, JSON, YAML
- **Quality gates** — Ruff, mypy, pytest, pytest-cov, pip-audit, gitleaks

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Architecture

```text
Codex / Claude Code / CLI / MCP / Dashboard
                    │
                    ▼
             Alcove Application
                    │
   ┌────────────────┼────────────────┐
   │                │                │
Managed KBs   Global Memory   External Indexes
 inbox          pins           mounts
 archive        prompts        connectors
 OKF notes      tasks          fetch refs
 validation     projects       OKF mirrors
   │                │                │
   └────────────────┼────────────────┘
                    ▼
       Global OKF Catalog / Search Rows
                    │
        Dashboard / Publishers / Service
```

Key design rules:

- **Reads are broad.** Agents can search, inspect OKF files, follow source refs,
  fetch connector details, and read mounted evidence.
- **Writes are narrow.** Durable mutations should go through Alcove CLI/MCP so
  frontmatter, provenance, indexes, activity logs, and health checks remain
  consistent.
- **Derived files are disposable.** Rebuild dashboard snapshots, usage rollups,
  JSON indexes, and OKF catalogs from source-of-truth data.

See [docs/architecture.md](docs/architecture.md) and
[docs/read-write-model.md](docs/read-write-model.md) for the full model.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Getting Started

### Installation

```sh
uv tool install git+https://github.com/OctopusGarage/alcove.git
alcove --version
```

For local development:

```sh
git clone https://github.com/OctopusGarage/alcove.git
cd alcove
uv sync
uv run alcove --version
uv tool install --force -e .
```

### First Setup

```sh
alcove home init
alcove kb add research_notes /path/to/research_notes
alcove hub init ~/AlcoveHub --default-kb research_notes
alcove hub install ~/AlcoveHub --default-kb research_notes
alcove global install --default-kb research_notes
alcove kb install research_notes
```

Entry profiles:

| Mode | Purpose |
| --- | --- |
| Hub workspace | Main AI workspace for broad personal knowledge work. |
| Global MCP | Lightweight search/save access from unrelated projects. |
| Managed KB workspace | Focused capture, inbox review, and OKF note workflows. |
| Local service | launchd dashboard server and deterministic scheduler ticks. |

Development link mode keeps Alcove-owned skills and commands symlinked to the
repository templates:

```sh
alcove hub install ~/AlcoveHub --default-kb research_notes --link
alcove kb install research_notes --link
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Core Workflows

### Managed KB

```sh
alcove inbox --kb research_notes peek
alcove inbox --kb research_notes manual-add "Manual Thought" \
  --content "Copied note text" \
  --source "chat://manual"
alcove knowledge --kb research_notes note-source \
  --platform web \
  --title "Example" \
  --topic agent-engineering/agent-harness \
  --summary "Summary"
alcove search "Example" --kb research_notes
```

### Global Memory

```sh
alcove pin add "Useful Pattern" --description "Short reusable note" --tag reference
alcove prompt save "Code Review Lens" --content "Review for correctness." --tag review
alcove task add "Wire MCP search" --priority high --tag mcp
alcove project add alcove /path/to/alcove --note "Personal information core"
```

### External Indexes

```sh
alcove mount add /path/to/repos --name repos --type local-folder --tag repos
alcove mount scan repos --json
alcove connector github-stars import-url "https://github.com/octocat?tab=stars" --json
alcove connector chrome-bookmarks import-local --tag bookmarks --json
alcove connector apple-notes import-local --tag apple-notes --json
alcove connector status --json
```

### Radars, Watchers, and Blogs

```sh
alcove radar preset list --json
alcove radar init tech-news --from-preset tech-news --json
alcove radar run tech-news --force --ai --notify --json
alcove watch add "Example Blog" https://example.com/feed.xml --kind rss --kb research_notes
alcove blog check --stale --json
```

### Dashboard and Publishers

```sh
alcove dashboard --home ~/.alcove build
alcove serve --dashboard --home ~/.alcove --port 8765
alcove publish init apple-notes --root-folder "iCloud/Alcove" --json
alcove publish run apple-notes --json
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Operations

Run a normal health check:

```sh
alcove health --home ~/.alcove --json
alcove health --home ~/.alcove --kb research_notes --fix --json
```

Run a local full-maintenance pass:

```sh
alcove health --home ~/.alcove --fix --deep --json
```

`--deep` rescans mounts, rebuilds usage rollups, rebuilds the dashboard snapshot,
and rebuilds the global OKF catalog. Connector refresh remains explicit:

```sh
alcove health --home ~/.alcove --fix --deep --refresh-stale-connectors --json
```

Serve deterministic background work through launchd:

```sh
alcove service install --dashboard --scheduler --load
alcove service status
alcove service tick --json
```

Back up managed KB roots and `~/.alcove` outside the Alcove runtime. Recommended
tools:

- scheduled Git sync: https://github.com/OctopusGarage/git-auto-sync
- optional Git encryption: https://github.com/AGWA/git-crypt

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Documentation

- [Documentation Index](docs/README.md)
- [Usage Guide](docs/usage.md)
- [Entry Modes](docs/entry-modes.md)
- [Architecture](docs/architecture.md)
- [Modules](docs/modules.md)
- [OKF Profile](docs/okf-profile.md)
- [Read/Write Model](docs/read-write-model.md)
- [Data and Backup](docs/data-and-backup.md)
- [Coverage Setup](docs/coverage.md)
- [Smoke and Agent Eval](docs/evals/local-smoke.md)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Development

```sh
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
scripts/verify/check.sh
```

Coverage is generated as `coverage.xml` by pytest and uploaded in CI from the
Ubuntu matrix job. See [docs/coverage.md](docs/coverage.md) for Codecov setup.

## License

Distributed under the MIT License. See [LICENSE](LICENSE).

<p align="right">(<a href="#readme-top">back to top</a>)</p>
