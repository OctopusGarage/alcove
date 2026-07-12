import { currentRoute, routes } from "../router";
import type { DashboardSnapshot } from "../snapshot";
import { formatSingaporeDateTime } from "./date";
import { escapeHtml } from "./text";

export function layout(snapshot: DashboardSnapshot, content: string): string {
  const route = currentRoute();
  const nav = routes
    .map(
      (item) => `
        <a class="nav-item ${item.path === route ? "active" : ""}" href="#${item.path}">
          <span>${escapeHtml(item.label)}</span>
          <small>${escapeHtml(item.description)}</small>
        </a>`,
    )
    .join("");
  return `
    <header class="topbar">
      <a class="brand" href="#/">
        <span class="brand-mark">A</span>
        <span><b>Alcove</b><small>local index cabinet</small></span>
      </a>
      <nav>${nav}</nav>
      <div class="topbar-actions">
        <button class="refresh-button" type="button" data-refresh-dashboard>
          Refresh
        </button>
        <div class="snapshot-meta" aria-live="polite">
          <span>Snapshot · Singapore time</span>
          <b data-snapshot-generated-at>${escapeHtml(formatSingaporeDateTime(snapshot.generated_at, { seconds: true }))}</b>
          <code data-snapshot-home>${escapeHtml(snapshot.home)}</code>
        </div>
      </div>
    </header>
    <main class="main">${content}</main>
  `;
}
