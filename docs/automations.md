# Automations

Automations are user-owned repeatable jobs under `~/.alcove/automations/`.
They run user-defined shell, git-sync, Alcove CLI, and guarded agent jobs.

```text
~/.alcove/automations/
├── jobs/*.yml                 job definitions and latest run state
├── runs/*.json                per-run audit records
└── events.jsonl               append-only run events
```

## Job Types

- `shell`: run a user-defined local shell command.
- `git-sync`: commit and push changes in a configured Git repository.
- `alcove`: run an Alcove CLI command as a repeatable local job.
- `agent`: run `claude -p` or `codex exec` with a stored prompt.

`agent` jobs are intentionally guarded. `alcove automation run-due` and
`alcove service tick` do not run them unless the job explicitly has
`allow_service: true` or the manual command passes `--allow-agent`. This keeps
background launchd work from silently depending on an open Codex/Claude session
or starting expensive AI workflows unexpectedly.

## Commands

```sh
alcove automation list --home ~/.alcove --json
alcove automation add-shell "backup cache" \
  --cmd "rsync -a ~/source/ ~/backup/" \
  --ttl-hours 24 \
  --json
alcove automation add-git-sync notes ~/notes \
  --commit-message "chore: sync notes" \
  --notify \
  --json
alcove automation run notes --json
alcove automation run-due --json
```

`run-due` respects each job's `ttl_hours` and latest `checked_at`. It is the
path used by `alcove service tick`.

## Notifications

Each job can include:

```yaml
notify:
  enabled: true
  on: failure      # failure or always
  sinks:
    - type: telegram
    - type: feishu
      webhook_env: ALCOVE_FEISHU_WEBHOOK_URL
    - type: tcb
      channel: feishu
```

Telegram credentials can be provided through environment variables or
`~/.alcove/.env`. Feishu custom webhooks send text notifications. The `tcb`
sink delegates richer delivery to a running
[`tmux-claude-bot`](https://github.com/OctopusGarage/tmux-claude-bot) service.

## Service Behavior

`alcove service tick` runs due automations after scheduled radar checks and
before OKF/health/dashboard refresh. Use `--skip-automations` to disable this
part of a manual tick.

```sh
alcove service tick --home ~/.alcove --skip-automations --json
```

Scheduled automations are meant for deterministic maintenance, data export, and
backup tasks. User-facing knowledge synthesis should still happen through Hub,
KB, or MCP workflows where an agent can inspect evidence and ask for judgment
when needed.
