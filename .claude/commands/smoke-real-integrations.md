---
description: Run Alcove's high-cost real external integration smoke.
allowed-tools: Bash, Read
---

Run the high-cost real integration smoke.

This uses an isolated `.tmp/real-integrations` Alcove Home and KB, but it does
real external work:

- GitHub Stars network import
- local Notes.app export
- Clipsmith web capture
- local macOS Vision OCR capture
- inbox sink/read
- MCP stdio server tool calls

Command:

```bash
repo="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$repo"
scripts/smoke-real-integrations.sh
```

If Clipsmith is not cloned as a sibling directory, set:

```bash
ALCOVE_CLIPSMITH_ROOT=/path/to/clipsmith scripts/smoke-real-integrations.sh
```

Report:

- pass/fail
- summary from `.tmp/real-integrations/real-integrations-summary.json`
- whether GitHub, Apple Notes, Clipsmith web, OCR, and MCP each passed
- first failing artifact path if failed

Do not run this automatically for small code edits. Use it when capture,
connectors, OCR, or MCP process boundaries changed, or when explicitly asked.
