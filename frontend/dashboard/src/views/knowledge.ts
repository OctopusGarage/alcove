import { emptyState } from "../components/empty-state";
import { formatSingaporeDateTime } from "../components/date";
import { asText, escapeHtml } from "../components/text";
import type { DashboardSnapshot } from "../snapshot";

export function renderKnowledge(snapshot: DashboardSnapshot): string {
  const managed = snapshot.knowledge_bases
    .map((kb) => {
      const title = asText(kb.name);
      const detail = `${asText(kb.item_count)} notes / ${asText(kb.inbox_count)} inbox / ${asText(kb.archive_count)} archived`;
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
      const detail = `${asText(item.connector) || "connector"} / ${asText(item.count)} indexed items`;
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
      const detail = `${asText(item.type)} / ${asText(item.count)} indexed items`;
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
    panel("Managed KBs", managed || emptyState("No managed KBs registered yet.")),
    panel("Connectors", connectors || emptyState("No connectors yet.")),
    panel("Mounts", mounts || emptyState("No mounts yet.")),
  ].join("");
  return `
    <header class="page-head">
      <p class="eyebrow">Knowledge system</p>
      <h1>Knowledge</h1>
      <p>Review managed KB inboxes, indexed external folders, and connector freshness before starting deeper local knowledge investigation.</p>
    </header>
    <section class="relationship">
      <div><b>Managed KBs</b><span>Writable knowledge roots with inbox, archive, notes, and OKF indexes.</span></div>
      <div><b>Mounts</b><span>Read-only local folders indexed for AI-led search and follow-up reading.</span></div>
      <div><b>Connectors</b><span>Protocol-based sources with refreshable indexes and lazy fetch details.</span></div>
    </section>
    <section class="module-list" data-filter-list data-filter-limit="24">
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

function panel(title: string, content: string): string {
  return `<div class="panel"><h2>${escapeHtml(title)}</h2>${content}</div>`;
}
