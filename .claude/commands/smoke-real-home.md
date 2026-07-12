---
description: Run Alcove's read-mostly smoke against the current ~/.alcove home.
allowed-tools: Bash, Read
---

Run the read-mostly smoke against the current machine's Alcove Home.

This reads `~/.alcove` and rebuilds only the derived dashboard snapshot. It must
not create, archive, refresh network connectors, or mutate user records.

Command:

```bash
repo="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$repo"
ALCOVE_REAL_SMOKE_REPORT_DIR=.tmp/real-home-smoke scripts/smoke-real-home.sh
```

Report:

- pass/fail
- summary counts from `.tmp/real-home-smoke/real-home-smoke-report.json`
- any failed check name and artifact path
