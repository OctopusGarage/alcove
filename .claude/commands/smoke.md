---
description: Run Alcove's isolated local smoke suite.
argument-hint: "[keep]"
allowed-tools: Bash, Read
---

Run Alcove's isolated local smoke suite from the repository root.

Use this by default after CLI, inbox, knowledge, pins, prompts, projects, tasks,
mounts, connectors, dashboard, export, or installer changes.

Command:

```bash
repo="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$repo"
scripts/smoke.sh
```

If `$ARGUMENTS` contains `keep`, preserve artifacts:

```bash
repo="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$repo"
ALCOVE_SMOKE_KEEP=1 scripts/smoke.sh
```

Report:

- pass/fail
- failing command and JSON artifact when failed
- whether artifacts were kept
- next fix or remaining untested area
