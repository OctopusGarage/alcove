# Automations

Automations are user-owned repeatable jobs under `~/.alcove/automations/`.
They replace the generic user-task part of legacy Social Radar without making
Social Radar's specific Python task modules part of Alcove core.

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
alcove automation import-social-radar ~/.social_radar --home ~/.alcove --json
```

`run-due` respects each job's `ttl_hours` and latest `checked_at`. It is the
path used by `alcove service tick`.

## Legacy Social Radar Mapping

`import-social-radar` reads `~/.social_radar/config/tasks.json`.

- `git_repos[]` becomes `git-sync` automation jobs.
- supported `ClaudeTask` modules become `agent` automation jobs with
  `allow_service: false` by default.
- unsupported arbitrary Python tasks are reported as skipped and must be
  reviewed manually.

This is deliberate. Alcove stores the durable intent and repeatability contract,
but does not import arbitrary executable Python as trusted background code.

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
