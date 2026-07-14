# Agent Workspaces

Agent workspaces are AI conversation directories. They are separate from
Alcove Home and from managed knowledge-base roots.

```text
Alcove Entry Modes
├── Global Lite MCP              lightweight access from unrelated projects
├── Hub Workspace                fixed control workspace
│   └── Business Workspaces      lightweight scene-specific workspaces
└── Managed KB                   capture, inbox, archive, OKF notes
```

## Concepts

```text
Alcove Home (~/.alcove)
└── global data, registries, indexes, service state

Managed KB
└── user-chosen knowledge root with inbox/archive/knowledge/todo

Agent Workspace
└── directory opened by Codex or Claude Code to inherit AGENTS.md, CLAUDE.md,
    and project skills
```

The fixed `hub` workspace is special. It is the system control surface and uses
the full `alcove-hub` skill. Custom workspaces such as `family`, `work`, or
`travel` use the lightweight `alcove-workspace` skill.

## Storage

```text
~/.alcove/
├── workspaces/
│   ├── hub.yml                  Hub registry record
│   ├── family.yml               custom workspace registry record
│   ├── work.yml
│   └── data/
│       ├── hub/                 default Hub directory if --path omitted
│       ├── family/              default custom workspace directory
│       └── work/
├── knowledge-bases/
├── pins/
├── tasks/
├── prompts/
└── ...
```

When `--path` is omitted, Alcove creates the agent directory at
`~/.alcove/workspaces/data/<id>/`. When `--path` is provided, the registry still
lives under `~/.alcove/workspaces/<id>.yml`, but the agent files are installed
in the chosen directory.

Custom workspace directory:

```text
<workspace-path>/
├── .alcove-workspace.yml
├── documents/                             workspace-local source files
├── okf/                                   workspace-local OKF managed store
├── AGENTS.md
├── CLAUDE.md
├── .agents/skills/alcove-workspace/SKILL.md
└── .claude/skills/alcove-workspace/SKILL.md
```

Hub directory:

```text
<hub-path>/
├── .alcove-hub.yml
├── AGENTS.md
├── CLAUDE.md
├── .agents/skills/alcove-hub/SKILL.md
└── .claude/skills/alcove-hub/SKILL.md
```

## Commands

Create or reinstall the fixed Hub:

```sh
alcove workspace init hub --default-kb social_media_posts
alcove workspace install hub --link
```

Create lightweight business workspaces:

```sh
alcove workspace init family \
  --default-kb social_media_posts \
  --tag family \
  --context "Family errands, household knowledge, and recurring reminders."

alcove workspace init work \
  --path ~/WorkHub \
  --default-kb work_notes \
  --tag work
```

Inspect and reinstall:

```sh
alcove workspace list --json
alcove workspace status family --json
alcove workspace install family --target all --link
```

Run a one-shot agent task inside a workspace:

```sh
alcove workspace run family --agent codex "整理家庭相关任务"
alcove workspace run work --agent claude "总结工作相关事项"
```

Use `--print-command` to inspect the command before running it:

```sh
alcove workspace run family --agent codex --print-command "整理家庭相关任务" --json
```

## Operating Rules

Hub workspace:

- owns system-wide routing and administration;
- can manage KBs, global MCP, mounts, connectors, radars, services, publishers,
  health fixes, exports, and entry installs;
- is the right place for Alcove project maintenance and cross-module work.

Custom business workspace:

- starts reads from configured preferred KBs, tags, and modules;
- can save scene-local manual inbox drafts, notes, pins, tasks, ideas, and
  prompt recommendations;
- preserves workspace tags/context on writes;
- does not perform Hub-only administration by default.

Long-running sessions should start in the workspace directory:

```sh
cd ~/.alcove/workspaces/data/family
codex
# or
claude
```

One-shot runs are suitable when the user wants a scoped task without manually
opening a new terminal session.

## Workspace OKF

Business workspaces can own a local OKF store. This is the preferred place for
scene-local documents, notes, and discussion summaries, such as family records,
household documents, travel planning, or work-specific notes.

The user-facing command is `workspace okf`; the implementation reuses Alcove's
managed-KB storage so validation, search, indexes, and OKF conventions stay
consistent.

```text
<workspace-path>/
├── documents/                 raw files the workspace owns or references
└── okf/                       managed KB root
    ├── .alcove/config.yml
    ├── inbox/
    ├── archive/
    ├── knowledge/
    └── todo/
```

Initialize workspace-local OKF:

```sh
alcove workspace okf init family --json
```

This creates `documents/`, initializes `okf/` as a managed KB, registers it in
`~/.alcove/knowledge-bases/<workspace-id>.yml`, and updates both the workspace
registry and `.alcove-workspace.yml` so `default_kb` points at the local OKF
store.

Add a structured note:

```sh
alcove workspace okf add-note family home/insurance "家庭保险资料整理" \
  --summary "家庭保险资料需要按保单、受益人、续费日期归档。" \
  --tag insurance \
  --json
```

Import a workspace file:

```sh
alcove workspace okf import-file family ./documents/insurance.md \
  --topic home/insurance \
  --json
```

Search only this workspace's OKF store:

```sh
alcove workspace okf search family "保单" --json
```

Check status:

```sh
alcove workspace okf status family --json
```

Operating rule: in a business workspace, "record this", "整理成笔记",
"查一下这个空间里的资料", and similar scene-local knowledge requests should
use `alcove workspace okf ...` first. Global pins, tasks, ideas, and prompts
remain global Alcove modules and should preserve the workspace tag.
