---
description: Run Alcove's AI quality eval across smoke, real integrations, and agent-facing flows.
argument-hint: "[provider: codex|claude|none] [skip-refresh]"
allowed-tools: Bash, Read
---

Run Alcove's AI quality eval from the repository root.

This eval is separate from deterministic smoke. It reruns smoke suites, builds
an AI review packet, then asks an AI reviewer to judge usefulness, intent fit,
module consistency, and agent-facing quality.

Command:

```bash
repo="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$repo"
scripts/eval-ai.sh
```

Options:

```bash
ALCOVE_AI_EVAL_PROVIDER=claude scripts/eval-ai.sh
ALCOVE_AI_EVAL_PROVIDER=none scripts/eval-ai.sh
ALCOVE_AI_EVAL_SKIP_REFRESH=1 scripts/eval-ai.sh
```

Report:

- pass/fail for deterministic setup
- AI verdict and score from `.tmp/ai-eval/ai-review.json`
- blocking and should-fix findings first
- files changed if fixes are made
