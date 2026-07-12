import { emptyState } from "../components/empty-state";
import { formatSingaporeDateTime } from "../components/date";
import { asText, escapeHtml } from "../components/text";
import type { DashboardSnapshot } from "../snapshot";

export function renderRadars(snapshot: DashboardSnapshot): string {
  const rows = snapshot.radars.map(radarRow).join("");
  return `
    <header class="page-head">
      <p class="eyebrow">Radars</p>
      <h1>Information Radars</h1>
      <p>Check active discovery feeds, deterministic scores, latest run state, and sources that need a manual refresh or AI follow-up review.</p>
    </header>
    <section class="module-list" data-filter-list data-filter-limit="16">
      ${moduleToolbar("Search radars")}
      <div class="list" data-filter-items>
        ${rows || emptyState("No radars configured yet.")}
      </div>
    </section>
  `;
}

function radarRow(radar: Record<string, unknown>): string {
  const id = asText(radar.id);
  const name = asText(radar.name) || id || "Radar";
  const status = asText(radar.status) || "unknown";
  const sourceCount = asText(radar.source_count) || "0";
  const tags = Array.isArray(radar.tags) ? radar.tags.map((tag) => asText(tag)).filter(Boolean) : [];
  const schedule = asText(radar.schedule_enabled) === "true" ? "scheduled" : "manual";
  const lastRun = radarLastRunLabel(radar.last_run);
  const detail = [
    id,
    status,
    schedule,
    `${sourceCount} sources`,
    tags.join(", "),
    lastRun,
  ]
    .filter(Boolean)
    .join(" / ");
  return `
    <article class="row compact-row" data-filter-item data-kind="radar" data-filter-text="${escapeHtml([name, detail].join(" "))}">
      <div>
        <h2>${escapeHtml(name)}</h2>
        <p>${escapeHtml(detail)}</p>
      </div>
      <span class="badge">${escapeHtml(status)}</span>
    </article>
  `;
}

function radarLastRunLabel(value: unknown): string {
  if (!isRecord(value)) {
    return formatSingaporeDateTime(value);
  }
  const timestamp = value.generated_at || value.completed_at || value.started_at;
  return timestamp ? formatSingaporeDateTime(timestamp) : "No runs yet";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
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
