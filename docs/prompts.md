# Prompt Library

Alcove Prompt Library stores reusable instructions as governed personal memory.
It is not a dump of every historical AI input. Raw history is evidence; only
curated, reusable prompts should become active prompt records.

## Goals

- preserve high-quality reusable prompts in a stable OKF-compatible format;
- make prompts searchable by scenario, intent, surface, and domain;
- let agents recommend and compose prompts for loop engineering without guessing;
- keep write operations governed by CLI/MCP while leaving read exploration open;
- support batch curation from historical prompt folders without polluting the
  active library.

## Data Model

Prompt source of truth:

```text
~/.alcove/prompts/
├── <prompt-id>.md                 curated OKF-compatible prompt records
├── candidates/
│   └── index.json                 scanned candidates waiting for auto-promotion
└── index.json                     derived searchable prompt index
```

Each active prompt is Markdown with YAML frontmatter:

```yaml
type: Prompt
schema: okf/prompt/v1
title: Dashboard Regression Review
description: Review dashboard data consistency and missing tests.
kind: eval_prompt
domain: review
intent: review
surfaces:
  - codex
  - claude-code
  - generic-llm
tags:
  - review
  - dashboard
use_cases:
  - Dashboard review
triggers:
  - dashboard bug
inputs:
  - diff
  - requirements
outputs:
  - findings
source_refs:
  - source:prompt-guidelines
quality:
  status: curated
  score: 0.9
status: active
created_at: "2026-07-13T00:00:00+00:00"
updated_at: "2026-07-13T00:00:00+00:00"
```

The frontmatter is retrieval and governance metadata. The body under
`## Prompt` must be a copy-ready prompt that can be pasted into Codex, Claude
Code, or another LLM without the surrounding library record. Usage timing,
triggers, tags, output labels, surfaces, source references, and quality scores
belong in frontmatter, not inside the prompt body.

Supported `kind` values:

```text
full_prompt      complete prompt ready to copy or call
fragment         reusable partial block that is not a complete task prompt
modifier         suffix or constraint composed with another prompt
playbook         multi-step workflow prompt
eval_prompt      quality review or regression evaluation prompt
source_note      reference-only note, down-ranked in recommendations
```

Agent behavior preferences, terse-command mappings, and personal interaction
rules are not active prompt-library material. Keep them in the relevant agent
rules, hub skill, or archived/source notes. They may be useful evidence during
curation, but they should not appear as active prompts unless rewritten into a
copyable task prompt with a concrete output.

Prompt-library maintenance prompts are also not normal active prompts by
default. For example, prompts that only tell Alcove or an agent how to judge,
deduplicate, import, or clean other prompts belong in the governed
`propose`/`audit`/`candidates` flow, docs, tests, or archived reference records.
Keep them active only when the user explicitly wants to reuse that prompt as a
standalone task outside Alcove's built-in prompt-management workflow.

## Curation Flow

Historical prompt folders or AI input archives should be scanned into
candidates first:

```sh
alcove prompt candidates scan ~/path/to/prompt-archive ~/path/to/ai-input-archive --json
alcove prompt candidates list --min-score 0.72 --json
alcove prompt candidates promote --min-score 0.72 --json
```

The scanner extracts structured prompt blocks, style prompt fragments, and
playbook-like sections. It scores candidates using deterministic quality signals:
substantial reusable content, explicit constraints, output format, workflow
structure, and guardrails. Promotion writes normal prompt Markdown records and
rebuilds `~/.alcove/prompts/index.json`.

The scanner intentionally does not import raw chat logs directly. Large history
files should be summarized or classified first, then promoted as style profiles,
playbooks, or eval prompts only when the behavior is stable and reusable.

## Search And Recommendation

Exact search remains available:

```sh
alcove prompt search "regression review" --tag review --kind eval_prompt --json
alcove prompt get dashboard-regression-review
alcove prompt audit --json
```

Scenario recommendation is the main agent-facing read path:

```sh
alcove prompt recommend "I need to fix a dashboard data bug and verify no regression" --json
alcove prompt compose "I need to fix a dashboard data bug and verify no regression"
```

Recommendation returns at most five ranked prompt ids by default, with reasons,
kind, domain, intent, tags, use cases, surfaces, and paths. Agents should show
the numbered candidates to the user, let the user choose one or more, and inspect
the full prompt with `prompt get` before copying or applying it.
Recommendation intentionally prefers precision over filler. Weak content-only
matches are filtered out; returning no prompt is better than suggesting a barely
related prompt. Terse-command mappings such as "continue" or "push it" belong in
agent rules/source notes, not in the active prompt library.

Composition returns a ready-to-use Prompt Pack assembled from the best matching
records. It is deterministic and includes source ids, match reasons, selected
prompt excerpts, operating instructions, and a final task section. Use it when a
user wants the next AI turn to apply the library directly:

```sh
alcove prompt compose "review dashboard data consistency after refactor" \
  --surface codex \
  --limit 4
```

`compose` is still a read operation. It does not create a new prompt record; if
the composed result becomes reusable, save the refined version with
the proposal-first write flow below.

The first recommendation engine is deterministic. It scores title, description,
intent, domain, triggers, use cases, tags, and prompt content, then adjusts by
curation quality. The interface is intentionally stable so a later AI reranker or
embedding index can be added without changing CLI/MCP contracts.

## Quality Standard

Alcove treats a prompt as a reusable instruction, not as a raw note, chat
fragment, or decorative template. The standard follows current first-party
prompt engineering guidance:

- OpenAI describes prompt engineering as writing instructions that consistently
  produce outputs meeting requirements, and recommends tests/evals when prompts
  change: <https://developers.openai.com/api/docs/guides/prompt-engineering>
- Anthropic recommends starting with success criteria, empirical tests, and a
  first draft before prompt improvement:
  <https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/overview>
- Google Gemini guidance emphasizes clear instructions, context, examples, and
  consistent formatting:
  <https://ai.google.dev/gemini-api/docs/prompting-strategies>
- Microsoft system-message guidance highlights role/scope, output contract,
  safety constraints, fallback behavior, and realistic testing:
  <https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/advanced-prompt-engineering>

Every active prompt should answer four questions clearly:

```text
When to use it       the scenario, trigger, or user intent
What to do           concrete behavior in priority order
What to output       the expected result or artifact
What not to do       boundaries, failure cases, or privacy constraints
```

This does not require a fixed template. A good prompt can be a short paragraph
and a few bullets. Avoid boilerplate sections such as `Role and Purpose`,
`Required Inputs`, `Operating Rules`, `Output Contract`, and `Guardrails` unless
that structure is genuinely useful for the prompt.

Historical notes such as "the user often says X" are source material; they are
not ready prompts until rewritten into a copyable instruction with a concrete
task and output. If the material only describes how an agent should behave in a
conversation, archive it or move it to agent rules instead of keeping it in the
active prompt library.

Use AI eval during curation with these checks:

- Is this actually a prompt, or just a note, article summary, log, or one-off
  command?
- Would another agent know when to use it from title, description, tags, and
  triggers?
- Is the body short enough to read and direct enough to apply?
- Does it avoid personal paths, credentials, stale project names, and raw private
  context?
- Is there already an active prompt that should be updated instead?

Prompt quality is not only a deterministic schema check. Rules catch cheap
failure modes such as missing metadata, duplicate records, metadata-card bodies,
or personal paths. Reusable prompt quality also needs a reviewer-style eval that
judges professional clarity, logic, execution usefulness, and semantic closure.

Alcove therefore evaluates prompt proposals in two rounds:

1. **Professional quality review** checks whether the prompt body is copy-ready,
   direct, concise, free of metadata cards, explicit about outputs, and useful to
   another capable agent.
2. **Adversarial reuse review** checks whether every title/description promise is
   actually satisfied by the prompt body. If a prompt says "verify", "rerun",
   "harden", "codify", "preserve", "固化", or "复跑", the body must require
   concrete evidence, repeatable commands or steps, and durable artifacts such as
   tests, smoke checks, AI eval cases, docs, scripts, fixtures, prompts, or
   follow-up tasks.

This eval is intentionally separate from formatting rules. A prompt can be valid
Markdown and still fail quality eval if it is vague, logically incomplete,
over-templateized, or does not deliver the promise in its title.

## Hub-Assisted Write Flow

In the Hub entry, the current Codex or Claude Code agent is the first prompt
quality reviewer. The agent should not call another model by default just to
decide whether a pasted fragment is worth saving. The normal Hub flow is:

1. Classify the input as one of:
   - reusable prompt;
   - source material that should be rewritten into a reusable prompt;
   - duplicate or update to an existing prompt;
   - managed KB note, article summary, style rule, or raw chat fragment that
     should not become an active prompt.
2. Search before writing:

   ```sh
   alcove prompt recommend "<scenario>" --json
   ```

   If a similar active prompt exists, prefer updating or merging it instead of
   creating a noisy duplicate.
3. Rewrite the candidate into a concise, copy-ready prompt body. Keep usage
   timing, trigger words, tags, surfaces, source references, and expected
   outputs in metadata fields; do not put those record-card headings inside the
   prompt body.
4. Run proposal-first validation:

   ```sh
   alcove prompt propose "<title>" --content "..." --json
   ```

5. Inspect `action`, `similar`, `warnings`, `evaluation`,
   `evaluation.prompt_ai_eval.rounds`, and the optimized `request`.
6. Revise and propose again when `must_fix` is non-empty, when either
   `professional_quality` or `adversarial_reuse` fails, or when the optimized
   body is not something another agent could copy directly.
7. Save only accepted proposals:

   ```sh
   alcove prompt save --proposal-id <proposal-id> --json
   ```

Use `--ai-eval-provider codex` or `--ai-eval-provider claude` only when a
separate model review is explicitly wanted. That external review is optional
and slower; the default guardrail is the current agent's review plus the
deterministic proposal eval.

## Governed Write Flow

Prompt writes are proposal-first by default. Do not save raw pasted text directly
into the active library.

```sh
alcove prompt propose "Dashboard Regression Review" \
  --content "Review the current diff for regressions..." \
  --tag review \
  --json

alcove prompt propose "Dashboard Regression Review" \
  --content "Review the current diff for regressions..." \
  --ai-eval-provider codex \
  --json

alcove prompt proposal <proposal-id> --json
alcove prompt save --proposal-id <proposal-id> --json
```

`propose` performs the write-time checks that agents should not hand-roll:

- cleans the title and prompt body;
- converts detailed personal local source paths into stable source labels;
- fills missing description, use cases, surfaces, triggers, inputs, outputs,
  kind, domain, intent, tags, and quality metadata when reasonable;
- finds up to five similar active prompts;
- recommends an action:
  - `create_new`
  - `create_new_after_review`
  - `update_existing`
  - `merge_into_existing`
  - `reject_as_one_off`
  - `save_as_knowledge_note_not_prompt`
- returns an explicit `evaluation` block with verdict, quality score, findings,
  dedupe status, metadata completeness checks, source warnings, and whether the
  optimized body has a professional reusable prompt contract;
- includes a prompt-specific `prompt_ai_eval` block with the two review rounds,
  must-fix items, suggestions, and the reviewer prompt contract used for
  Codex/Claude-backed quality review.

`save --proposal-id` accepts the optimized prompt request from the proposal.
For `update_existing`, it merges the optimized request into the highest-
confidence similar prompt instead of creating a second active record or
blindly replacing the old prompt. Existing reusable instructions, triggers,
outputs, tags, and source refs are preserved unless the new proposal genuinely
supersedes duplicate content. It refuses `merge_into_existing`,
`reject_as_one_off`, and `save_as_knowledge_note_not_prompt` proposals, because
those require explicit human or agent review before changing the library. It
also refuses proposals whose `evaluation.verdict` is not `ready` or
`update_existing`. Chat fragments, historical interaction rules, article notes,
and weak one-off instructions must be rewritten or stored as managed KB notes
instead of becoming active prompts. Use `prompt save --force ...` only for
explicit repair scripts, tests, or operator-confirmed direct writes.

Every save returns a `prompt_eval` block with the saved prompt's post-write audit
verdict, prompt-level issues, global audit status, quality score, proposal id,
and whether force mode was used. Agents should show or inspect this block after
write/update operations. In normal proposal mode, unready prompts are blocked
before writing; a `needs_review` verdict should only appear after explicit
`--force` writes or legacy data repair.

For MCP clients, use the same sequence:

```text
alcove_prompt_propose -> alcove_prompt_proposal -> alcove_prompt_save
```

`alcove_prompt_save` accepts either `proposal_id` or `force: true`; without one
of those it returns an error instead of blindly writing.

Prompt import should be followed by a quality audit:

```sh
alcove prompt audit --json
```

Audit is read-only. It checks for:

- missing description, use cases, domain, outputs, or surfaces;
- duplicate active prompt content and similar titles;
- short content that is unlikely to be reusable;
- weak prompt bodies that look like historical notes instead of reusable
  instructions;
- over-templated prompt bodies that hide the useful behavior behind boilerplate;
- unportable source references that should use `~` or stable relative paths;
- personal local source references that should be replaced with stable
  `source:...` labels;
- average prompt quality score and how many records are ready for direct reuse.

Treat `surface_neutral` as informational. A generic prompt may intentionally omit
surfaces so it can be recommended for Codex, Claude Code, or other agents.
Warnings should be fixed first for high-value prompts; low-value prompt fragments
should be expanded or archived instead of kept as noisy active records.

## MCP Contract

MCP exposes lightweight prompt operations:

```text
alcove_prompt_propose
alcove_prompt_proposal
alcove_prompt_save
alcove_prompt_search
alcove_prompt_recommend
alcove_prompt_compose
alcove_prompt_audit
alcove_prompt_get
alcove_prompt_archive
alcove_prompt_tags
alcove_prompt_rebuild_index
```

Candidate scan/promote is kept in the CLI for now because it is a heavier batch
operation over local files. Other projects should generally use MCP for saving,
searching, recommending, and reading prompts.

## Quality Rules

- Do not save article summaries as prompts.
- Do not save one-off project instructions as prompts unless they generalize.
- Keep `content` copy-ready. Do not put library metadata headings such as
  `用于`, `触发`, `输出`, `use case`, or `tags` into the prompt body when the
  same information belongs in frontmatter.
- Start with `prompt propose` for new prompts; inspect similar prompts before
  accepting a proposal.
- Prefer `update_existing` or `merge_into_existing` when the proposal finds a
  high-confidence overlap.
- Prefer a small curated library over a large noisy library.
- Keep active prompts focused on reusable agent work. Concrete business
  leftovers, one-off publishing tasks, or project-specific operating notes
  should be archived or moved to knowledge notes unless they are generalized
  into a durable domain playbook.
- Domain playbooks are acceptable only when the scenario is reusable across
  projects, the output contract is clear, and the prompt avoids platform,
  account, local path, or historical-project assumptions.
- Store source references with `~` paths or stable relative references, never
  machine-specific absolute paths in docs or UI output.
- `fragment` prompts should be short and clearly composable.
- `modifier` prompts should have clear triggers, inputs, and expected effects
  because they are usually appended to another task prompt.
- Agent style profiles and terse-command mappings should not be active prompts;
  keep them as source notes or agent rules.
- `eval_prompt` records should state what quality or regression they judge.
