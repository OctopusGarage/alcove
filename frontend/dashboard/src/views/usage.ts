import { emptyState } from "../components/empty-state";
import { formatSingaporeDateTime } from "../components/date";
import { asText, escapeHtml } from "../components/text";
import type { DashboardSnapshot } from "../snapshot";

export function renderUsage(snapshot: DashboardSnapshot): string {
  const usage = snapshot.usage;
  const health = snapshot.health;
  const search = usage.search;
  const zeroRate = Math.round((search.zero_result_rate || 0) * 100);
  return `
    <header class="page-head">
      <p class="eyebrow">Usage</p>
      <h1>Usage</h1>
      <p>Local Alcove telemetry for search health, action distribution, and data-source status. Raw search text and content snippets are not logged by default.</p>
    </header>
    <section class="usage-hero">
      ${metric("Usage events", usage.total_events, "local non-content events")}
      ${metric("Searches", search.total, `${search.zero_result} zero-result searches / ${zeroRate}%`)}
      ${metric("Actions", usage.actions.total, "writes, refreshes, and index actions")}
      ${metric("Data sources", health.data_sources.length, healthStatusLabel(health.status, health.issue_count))}
      ${metric("Indexed items", indexedTotal(health.totals), "managed KBs, mounts, and connectors")}
      ${metric("Daily rollups", health.stats.daily_rollups, health.stats.summary_exists ? "summary available" : "waiting for summary")}
    </section>
    <section class="panel">
      <div class="panel-head"><h2>Data Health</h2><span class="row-meta">managed kb / mounts / connectors</span></div>
      <div class="list">${health.data_sources.map(dataSourceRow).join("") || emptyState("No data sources yet.")}</div>
    </section>
    <section class="usage-grid">
      <div class="panel">
        <div class="panel-head"><h2>Search Surfaces</h2><span class="row-meta">surface split</span></div>
        ${barList(search.surfaces, search.total)}
      </div>
      <div class="panel">
        <div class="panel-head"><h2>Search Types</h2><span class="row-meta">filters</span></div>
        ${barList(search.types, search.total)}
      </div>
      <div class="panel">
        <div class="panel-head"><h2>Dashboard Routes</h2><span class="row-meta">when served through Alcove</span></div>
        ${barList(usage.dashboard.routes, usage.total_events)}
      </div>
      <div class="panel">
        <div class="panel-head"><h2>Action Areas</h2><span class="row-meta">writes and refreshes</span></div>
        ${barList(usage.actions.areas, usage.actions.total)}
      </div>
      <div class="panel">
        <div class="panel-head"><h2>Action Names</h2><span class="row-meta">semantic actions</span></div>
        ${barList(usage.actions.names, usage.actions.total)}
      </div>
    </section>
    <section class="panel">
      <div class="panel-head"><h2>Recent Usage Events</h2><span class="row-meta">privacy-safe</span></div>
      <div class="list">${usage.recent.map(eventRow).join("") || emptyState("No usage events yet.")}</div>
    </section>
  `;
}

function metric(label: string, value: number, detail: string): string {
  return `
    <article class="usage-metric">
      <span>${escapeHtml(label)}</span>
      <b>${escapeHtml(value)}</b>
      <small>${escapeHtml(detail)}</small>
    </article>
  `;
}

function barList(values: Record<string, number>, total: number): string {
  const entries = Object.entries(values).sort((left, right) => right[1] - left[1]);
  if (!entries.length) {
    return emptyState("No data yet.");
  }
  return `
    <div class="usage-bars">
      ${entries
        .map(([label, value]) => {
          const percent = total > 0 ? Math.max(4, Math.round((value / total) * 100)) : 4;
          return `
            <div class="usage-bar">
              <div><b>${escapeHtml(label)}</b><span>${escapeHtml(value)} events</span></div>
              <i style="--value: ${percent}%"></i>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

function indexedTotal(totals: Record<string, number>): number {
  return (
    Number(totals.managed_items || 0) +
    Number(totals.mount_items || 0) +
    Number(totals.connector_items || 0)
  );
}

function healthStatusLabel(status: string, issueCount: number): string {
  if (status === "ok") {
    return "all data sources healthy";
  }
  return `${issueCount} data sources need attention`;
}

function dataSourceRow(row: Record<string, unknown>): string {
  const commandHint = asText(row.command_hint);
  return `
    <article class="row compact-row">
      <div>
        <h2>${escapeHtml(asText(row.name) || "Data source")}</h2>
        <p>${escapeHtml([asText(row.kind), asText(row.status), `${asText(row.item_count) || "0"} items`].filter(Boolean).join(" · "))}</p>
        ${
          commandHint
            ? `<details class="diagnostic-action">
                <summary>Diagnostic command</summary>
                <button type="button" data-copy-command="${escapeHtml(commandHint)}">${escapeHtml(commandHint)}</button>
              </details>`
            : ""
        }
      </div>
      <span class="row-meta">${escapeHtml(formatSingaporeDateTime(row.updated_at))}</span>
    </article>
  `;
}

function eventRow(event: Record<string, unknown>): string {
  const metrics = event.metrics && typeof event.metrics === "object" ? event.metrics : {};
  const metricText = [
    metricPair(metrics, "result_count", "results"),
    metricPair(metrics, "query_length", "query length"),
    metricPair(metrics, "duration_ms", "ms"),
  ]
    .filter(Boolean)
    .join(" / ");
  return `
    <article class="row compact-row">
      <div>
        <h2>${escapeHtml(asText(event.action) || "usage.event")}</h2>
        <p>${escapeHtml([asText(event.surface), asText(event.area), asText(event.outcome), metricText].filter(Boolean).join(" · "))}</p>
      </div>
      <span class="row-meta">${escapeHtml(formatSingaporeDateTime(event.timestamp))}</span>
    </article>
  `;
}

function metricPair(metrics: object, key: string, label: string): string {
  const value = (metrics as Record<string, unknown>)[key];
  const text = asText(value);
  return text ? `${label}: ${text}` : "";
}
