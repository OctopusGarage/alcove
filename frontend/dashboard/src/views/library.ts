import { emptyState } from "../components/empty-state";
import { asText, escapeHtml } from "../components/text";
import type { DashboardSnapshot } from "../snapshot";

export function renderLibrary(snapshot: DashboardSnapshot): string {
  const activePromptRecords = snapshot.prompts.filter((prompt) => isActivePrompt(prompt));
  const prompts = activePromptRecords.map((prompt, index) => promptCard(prompt, index));
  const projects = snapshot.projects.map((project) =>
    projectRow(
      asText(project.alias),
      [
        asText(project.note),
        asText(project.path_label),
        asText(project.exists) === "true" ? "exists" : "missing",
      ]
        .filter(Boolean)
        .join("\n"),
      "project",
    ),
  );
  const activePrompts = activePromptRecords.length;
  const domains = uniqueCount(activePromptRecords.map((prompt) => asText(prompt.domain) || "uncategorized"));
  const kinds = uniqueCount(activePromptRecords.map((prompt) => asText(prompt.kind) || "prompt"));
  return `
    <header class="page-head">
      <p class="eyebrow">Library</p>
      <h1>Prompt Library</h1>
      <p>Browse reusable prompts by purpose, domain, and expected output. Prompt source text stays intact, while import history and source references stay out of the primary reading path.</p>
    </header>
    <section class="library-ledger" aria-label="Prompt inventory">
      <div><b>${activePrompts}</b><span>active prompts</span></div>
      <div><b>${domains}</b><span>domains</span></div>
      <div><b>${kinds}</b><span>prompt kinds</span></div>
      <div><b>${snapshot.projects.length}</b><span>project shortcuts</span></div>
    </section>
    <section class="module-list" data-filter-list data-filter-label="prompts" data-filter-limit="all" data-filter-mobile-limit="all">
      ${moduleToolbar("Search prompts", [
        ["", "All"],
        ["full_prompt", "Full prompts"],
        ["playbook", "Playbooks"],
        ["eval_prompt", "Eval prompts"],
      ])}
      <div class="prompt-grid" data-filter-items>
        ${prompts.join("") || emptyState("No prompts yet.")}
      </div>
    </section>
    <section class="panel library-projects">
      <div class="panel-head"><h2>Project Shortcuts</h2><span class="row-meta">Local aliases for quick routing</span></div>
      <div class="list">${projects.join("") || emptyState("No project shortcuts yet.")}</div>
    </section>
  `;
}

function isActivePrompt(prompt: Record<string, unknown>): boolean {
  const kind = asText(prompt.kind);
  return asText(prompt.status) === "active" && kind !== "source_note" && kind !== "style_profile";
}

function promptCard(prompt: Record<string, unknown>, index: number): string {
  const title = asText(prompt.title) || asText(prompt.id) || "Untitled prompt";
  const kind = asText(prompt.kind) || "prompt";
  const domain = asText(prompt.domain) || "uncategorized";
  const intent = asText(prompt.intent);
  const status = asText(prompt.status) || "active";
  const content = asText(prompt.content).trim();
  const tags = textList(prompt.tags);
  const useCases = meaningfulList(prompt.use_cases, title);
  const triggers = textList(prompt.triggers);
  const outputs = textList(prompt.outputs);
  const surfaces = textList(prompt.surfaces);
  const description = displayDescription(prompt, content, useCases);
  const promptBodyId = `prompt-body-${index}-${domId(asText(prompt.id) || title)}`;
  const filterText = [
    title,
    description,
    content,
    kind,
    domain,
    intent,
    status,
    ...tags,
    ...useCases,
    ...triggers,
    ...outputs,
    ...surfaces,
  ].join(" ");

  return `
    <article class="prompt-card" data-filter-item data-kind="${escapeHtml(kind)}" data-filter-text="${escapeHtml(filterText)}">
      <div class="prompt-card-head">
        <div>
          <p class="prompt-kicker">${escapeHtml([domain, intent].filter(Boolean).join(" / "))}</p>
          <h2>${escapeHtml(title)}</h2>
        </div>
        <span class="badge">${escapeHtml(kindLabel(kind))}</span>
      </div>
      ${description ? `<p class="prompt-purpose">${escapeHtml(description)}</p>` : ""}
      <div class="prompt-facts">
        ${fact("Use when", useCases)}
        ${fact("Expected output", outputs)}
        ${fact("Trigger words", triggers)}
        ${fact("Surfaces", surfaces)}
      </div>
      <div class="prompt-preview">
        <div class="prompt-preview-topline">
          <div class="prompt-preview-label">Prompt</div>
          <button type="button" class="copy-button" data-copy-target="${escapeHtml(promptBodyId)}">Copy prompt</button>
        </div>
        <pre><code id="${escapeHtml(promptBodyId)}">${escapeHtml(content || "No prompt content.")}</code></pre>
      </div>
      ${tags.length ? `<div class="prompt-tags">${tags.slice(0, 8).map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</div>` : ""}
      <div class="prompt-card-foot">
        <span>${escapeHtml(status)}</span>
        <code>${escapeHtml(asText(prompt.id))}</code>
      </div>
    </article>
  `;
}

function moduleToolbar(label: string, filters: Array<[string, string]>): string {
  return `
    <div class="module-toolbar">
      <label>
        <span>${escapeHtml(label)}</span>
        <input class="module-filter-input" type="search" data-filter-input placeholder="Filter by scenario, tag, domain, or prompt text" />
      </label>
      <div class="quick-filters" aria-label="Prompt quick filters">
        ${filters
          .map(
            ([kind, filterLabel], index) => `
              <button
                type="button"
                data-filter-chip
                data-filter-kind="${escapeHtml(kind)}"
                ${index === 0 ? 'data-filter-reset="true"' : ""}
                ${index === 0 ? 'aria-pressed="true"' : 'aria-pressed="false"'}
              >${escapeHtml(filterLabel)}</button>
            `,
          )
          .join("")}
      </div>
      <div class="module-toolbar-actions">
        <span data-filter-count></span>
        <button type="button" data-filter-toggle>Show all</button>
      </div>
    </div>
  `;
}

function fact(label: string, values: string[]): string {
  if (values.length === 0) {
    return "";
  }
  return `
    <div>
      <span>${escapeHtml(label)}</span>
      <p>${escapeHtml(values.slice(0, 3).join(" / "))}</p>
    </div>
  `;
}

function displayDescription(
  prompt: Record<string, unknown>,
  content: string,
  useCases: string[],
): string {
  const description = asText(prompt.description).trim();
  const firstLine = content.split(/\n+/).map((line) => line.trim()).find(Boolean) ?? "";
  if (!description) {
    return useCases[0] ?? "";
  }
  const normalizedDescription = normalizeDisplayText(description);
  const normalizedFirstLine = normalizeDisplayText(firstLine);
  if (
    normalizedDescription &&
    (normalizedDescription === normalizedFirstLine ||
      normalizedFirstLine.startsWith(normalizedDescription) ||
      isWeakDescription(description))
  ) {
    return useCases[0] ?? "";
  }
  return description;
}

function isWeakDescription(value: string): boolean {
  const text = value.trim();
  return (
    /^you are\b/i.test(text) ||
    /^\[.+\]$/.test(text) ||
    /^从历史\s*AI\s*对话/.test(text) ||
    /^回顾我最近\s*\d+\s*天/.test(text)
  );
}

function meaningfulList(value: unknown, title: string): string[] {
  return textList(value).filter((item) => {
    const normalized = normalizeDisplayText(item);
    if (!normalized) {
      return false;
    }
    if (normalized.includes(`scenario: ${normalizeDisplayText(title)}`)) {
      return false;
    }
    return ![
      "reuse this prompt for a matching work scenario",
      "run a reusable multi-step workflow",
      "evaluate quality and prevent prompt or workflow regression",
    ].includes(normalized);
  });
}

function textList(value: unknown): string[] {
  if (!Array.isArray(value) || value.length === 0) {
    return [];
  }
  return value.map((item) => asText(item).trim()).filter(Boolean);
}

function projectRow(title: string, detail: string, badge: string): string {
  return `
    <article class="row compact-row">
      <div><h2>${escapeHtml(title)}</h2><p>${escapeHtml(detail)}</p></div>
      <span class="badge">${escapeHtml(badge)}</span>
    </article>
  `;
}

function uniqueCount(values: string[]): number {
  return new Set(values.filter(Boolean)).size;
}

function normalizeDisplayText(value: string): string {
  return value.replace(/\s+/g, " ").trim().toLowerCase();
}

function kindLabel(kind: string): string {
  return kind.replaceAll("_", " ");
}

function domId(value: string): string {
  const normalized = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return normalized || "prompt";
}
