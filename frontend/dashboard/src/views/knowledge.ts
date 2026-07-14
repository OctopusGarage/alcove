import { emptyState } from "../components/empty-state";
import { formatSingaporeDateTime } from "../components/date";
import { asText, escapeHtml } from "../components/text";
import type { DashboardSnapshot } from "../snapshot";

export function renderKnowledge(snapshot: DashboardSnapshot): string {
  const managed = snapshot.knowledge_bases
    .map((kb) => {
      const title = asText(kb.name);
      const detail = `${asText(kb.item_count)} notes / ${asText(kb.inbox_count)} inbox items / ${asText(kb.archive_count)} archived items`;
      return `
        <article class="row" data-filter-item data-kind="managed-kb" data-filter-text="${escapeHtml([title, detail, "managed KB"].join(" "))}">
          <div>
            <h2>${escapeHtml(title)}</h2>
            <p>${escapeHtml(detail)}</p>
          </div>
          <span class="row-meta">managed KB</span>
        </article>`;
    })
    .join("");
  const connectors = snapshot.sources.connectors
    .map((item) => {
      const title = asText(item.id);
      const itemCount = asText(item.item_count) || asText(item.count) || "0";
      const detail = `${asText(item.connector) || "connector"} / ${itemCount} indexed items`;
      const source = asText(item.source);
      return `
        <article class="row compact-row" data-filter-item data-kind="connector" data-filter-text="${escapeHtml([title, detail, source, "connector"].join(" "))}">
          <div>
            <h2>${escapeHtml(title)}</h2>
            <p>${escapeHtml(detail)}</p>
            <code>${escapeHtml(source)}</code>
          </div>
          <span class="row-meta">${escapeHtml(formatSingaporeDateTime(item.updated_at))}</span>
        </article>`;
    })
    .join("");
  const mounts = snapshot.sources.mounts
    .map((item) => {
      const title = asText(item.name);
      const itemCount = asText(item.item_count) || asText(item.count) || "0";
      const previewCount = asText(item.preview_count);
      const previewDetail = previewCount ? ` / ${previewCount} preview items` : "";
      const detail = `${asText(item.type)} / ${itemCount} indexed items${previewDetail}`;
      const status = asText(item.status);
      return `
        <article class="row compact-row" data-filter-item data-kind="mount" data-filter-text="${escapeHtml([title, detail, status, "mount"].join(" "))}">
          <div>
            <h2>${escapeHtml(title)}</h2>
            <p>${escapeHtml(detail)}</p>
          </div>
          <span class="row-meta">${escapeHtml(status)}</span>
        </article>`;
    })
    .join("");
  const rows = [
    panel("Managed KBs", managed || emptyState("No managed KBs registered yet."), "knowledge-managed"),
    panel("Connectors", connectors || emptyState("No connectors yet."), "knowledge-connectors"),
    panel("Mounts", mounts || emptyState("No mounts yet."), "knowledge-mounts"),
  ].join("");
  return `
    <header class="page-head">
      <p class="eyebrow">Knowledge system</p>
      <h1>Knowledge</h1>
      <p>Review managed KB inboxes, indexed external folders, and connector freshness before starting deeper local knowledge investigation.</p>
      ${pageJumps([
        ["knowledge-managed", "Managed KBs"],
        ["knowledge-connectors", "Connectors"],
        ["knowledge-mounts", "Mounts"],
      ])}
    </header>
    <section class="relationship">
      <div><b>Managed KBs</b><span>Writable knowledge roots with inbox, archive, notes, and OKF indexes.</span></div>
      <div><b>Mounts</b><span>Read-only local folders indexed for AI-led search and follow-up reading.</span></div>
      <div><b>Connectors</b><span>Protocol-based sources with refreshable indexes and lazy fetch details.</span></div>
    </section>
    <section class="module-list" data-filter-list data-filter-label="sources" data-filter-limit="24">
      ${moduleToolbar("Search knowledge sources")}
      <div class="source-columns" data-filter-items>${rows}</div>
    </section>
  `;
}

function moduleToolbar(label: string): string {
  return `
    <div class="module-toolbar">
      <label>
        <span>${escapeHtml(label)}</span>
        <input class="module-filter-input" type="search" data-filter-input placeholder="Filter this view" />
      </label>
      <div class="module-toolbar-actions">
        <span data-filter-count></span>
        <button type="button" data-filter-toggle>Show all</button>
      </div>
    </div>
  `;
}

function pageJumps(items: Array<[string, string]>): string {
  return `
    <div class="page-jumps" aria-label="Knowledge section jumps">
      ${items.map(([target, label]) => `<button type="button" data-page-jump="${escapeHtml(target)}">${escapeHtml(label)}</button>`).join("")}
    </div>
  `;
}

function panel(title: string, content: string, id: string): string {
  return `<div id="${escapeHtml(id)}" class="panel jump-panel" tabindex="-1"><h2>${escapeHtml(title)}</h2>${content}</div>`;
}
