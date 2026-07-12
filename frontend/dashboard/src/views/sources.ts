import { emptyState } from "../components/empty-state";
import { formatSingaporeDateTime } from "../components/date";
import { asText, escapeHtml } from "../components/text";
import type { DashboardSnapshot } from "../snapshot";

export function renderSources(snapshot: DashboardSnapshot): string {
  const connectors = snapshot.sources.connectors.map((item) =>
    row(
      asText(item.id),
      `${asText(item.count)} connector items`,
      `Updated ${formatSingaporeDateTime(item.updated_at)}`,
    ),
  );
  const mounts = snapshot.sources.mounts.map((item) =>
    row(asText(item.name), asText(item.type), "Read-only mounted source"),
  );
  return `
    <header class="page-head">
      <p class="eyebrow">External sources</p>
      <h1>Connectors and Mounts</h1>
      <p>External knowledge sources stay in place. Alcove reads their local indexes and presents one unified entry point.</p>
    </header>
    <section class="source-columns">
      <div class="panel"><h2>Connectors</h2>${connectors.join("") || emptyState("No connectors yet.")}</div>
      <div class="panel"><h2>Mounts</h2>${mounts.join("") || emptyState("No mounts yet.")}</div>
    </section>
  `;
}

function row(title: string, detail: string, meta: string): string {
  return `
    <article class="row compact-row">
      <div><h2>${escapeHtml(title)}</h2><p>${escapeHtml(detail)}</p></div>
      <span class="row-meta">${escapeHtml(meta)}</span>
    </article>
  `;
}
