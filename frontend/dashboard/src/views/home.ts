import { moduleCard } from "../components/module-card";
import { timeline } from "../components/timeline";
import type { DashboardSnapshot, ThemePin } from "../snapshot";
import { asText, escapeHtml } from "../components/text";

export function renderHome(snapshot: DashboardSnapshot): string {
  const counts = snapshot.summary.counts;
  const todoPins = snapshot.pins.themes.filter((pin) => pin.kind === "todo").slice(0, 4);
  const regularPins = snapshot.pins.themes.filter((pin) => pin.kind === "regular").slice(0, 4);
  return `
    <section class="home-hero">
      <div class="home-hero-copy">
        <p class="eyebrow">Local index</p>
        <h1>Daily Workbench</h1>
        <p class="lead">One snapshot for pins, planning, knowledge, and recent movement. The home view shows only decision-level state; complete records stay in their modules.</p>
        <div class="search-panel">
          <label for="global-search">Search this snapshot</label>
          <div class="search-row">
            <input id="global-search" class="search-input" placeholder="Search Alcove..." />
          </div>
          <div id="search-results" class="search-results"></div>
        </div>
      </div>
      <div class="home-ledger" aria-label="Alcove snapshot status">
        ${ledgerCell("Pin Records", counts.pins ?? 0, `${counts.theme_pins ?? 0} featured theme pins`)}
        ${ledgerCell("Tasks", counts.pending_tasks ?? 0, "pending tasks")}
        ${ledgerCell("Searchable", indexedTotal(counts), "indexed records")}
        ${ledgerCell("Source Coverage", countPhrase(sourceTotal(counts), "type"), sourceFamilyDetail(counts))}
      </div>
    </section>

    <section class="home-section">
      <div class="section-kicker">
        <span>Modules</span>
        <b>Entry points</b>
      </div>
      <div class="module-grid home-module-grid">${snapshot.modules.map(moduleCard).join("")}</div>
    </section>

    <section class="home-focus-grid">
      <div class="panel">
        <div class="panel-head"><h2>${todoPins.length ? "TODO Pins" : "Planner Queue"}</h2><a href="${todoPins.length ? "#/pins" : "#/planner"}">${todoPins.length ? "View pins" : "Open planner"}</a></div>
        ${todoPins.length ? pinRows(todoPins) : plannerFallback(snapshot)}
      </div>
      <div class="panel home-activity-panel">
        <div class="panel-head"><h2>Recent Activity</h2><a href="#/activity">Full timeline</a></div>
        ${timeline(snapshot.activity, { limit: 2, compact: true })}
      </div>
    </section>

    ${sourceHealth(snapshot)}

    ${regularPins.length ? regularThemePins(regularPins) : ""}
  `;
}

function ledgerCell(label: string, value: unknown, detail: string): string {
  return `
    <div class="ledger-cell">
      <span>${escapeHtml(label)}</span>
      <b>${escapeHtml(value)}</b>
      <small>${escapeHtml(detail)}</small>
    </div>
  `;
}

function indexedTotal(counts: Record<string, number>): number {
  return (
    Number(counts.knowledge_items || 0) +
    Number(counts.mount_items || 0) +
    Number(counts.connector_items || 0)
  );
}

function sourceTotal(counts: Record<string, number>): number {
  return (
    Number(counts.knowledge_bases || 0) +
    Number(counts.mounts || 0) +
    Number(counts.connectors || 0)
  );
}

function sourceFamilyDetail(counts: Record<string, number>): string {
  return [
    `Managed KBs: ${Number(counts.knowledge_bases || 0)}`,
    `Mounts: ${Number(counts.mounts || 0)}`,
    `Connectors: ${Number(counts.connectors || 0)}`,
  ].join("; ");
}

function countPhrase(count: number, singular: string): string {
  return `${count} ${count === 1 ? singular : `${singular}s`}`;
}

function pinRows(pins: ThemePin[]): string {
  return `
    <div class="home-pin-list">
      ${pins.map(pinRow).join("")}
    </div>
  `;
}

function pinRow(pin: ThemePin): string {
  const excerpt = pin.summary || pin.raw_excerpt || pin.content.slice(0, 220);
  return `
    <a class="home-pin-row ${pin.kind}" href="#/pins">
      <span>${escapeHtml(pin.kind === "todo" ? "TODO" : "PIN")}</span>
      <div>
        <h3>${escapeHtml(pin.title)}</h3>
        <p>${escapeHtml(excerpt)}</p>
      </div>
      <small>${escapeHtml(pin.priority)}</small>
    </a>
  `;
}

function empty(message: string): string {
  return `<div class="empty">${escapeHtml(message)}</div>`;
}

function regularThemePins(pins: ThemePin[]): string {
  return `
    <section class="panel">
      <div class="panel-head"><h2>Regular Theme Pins</h2><a href="#/pins">View all</a></div>
      ${pinRows(pins)}
    </section>
  `;
}

function sourceHealth(snapshot: DashboardSnapshot): string {
  const sources = snapshot.health.data_sources.slice(0, 6);
  if (!sources.length) {
    return "";
  }
  return `
    <section class="panel home-health">
      <div class="panel-head"><h2>Source Health</h2><a href="#/usage">View usage</a></div>
      <div class="home-health-grid">
        ${sources.map(sourceRow).join("")}
      </div>
    </section>
  `;
}

function sourceRow(row: Record<string, unknown>): string {
  return `
    <article>
      <span>${escapeHtml(asText(row.kind) || "source")}</span>
      <b>${escapeHtml(asText(row.name) || "Data source")}</b>
      <small>${escapeHtml([asText(row.status), `${asText(row.item_count) || "0"} items`].filter(Boolean).join(" · "))}</small>
    </article>
  `;
}

function plannerFallback(snapshot: DashboardSnapshot): string {
  const rows = [
    ...snapshot.tasks.pending.slice(0, 2).map((task) =>
      compactRow(
        asText(task.display_title) || asText(task.title),
        [
          asText(task.notes),
          taskMeta(
            ["priority", task.priority],
            ["due", task.due],
            ["state", task.due_state],
            ["overdue", task.overdue_days ? `${asText(task.overdue_days)} days` : ""],
          ),
        ]
          .filter(Boolean)
          .join("\n"),
        asText(task.due_state) || asText(task.status) || "task",
      ),
    ),
    ...snapshot.tasks.ideas.slice(0, 1).map((idea) =>
      compactRow(`Idea: ${asText(idea.title)}`, asText(idea.notes), "idea"),
    ),
    ...snapshot.tasks.routines.slice(0, 1).map((routine) =>
      compactRow(`Routine: ${asText(routine.title)}`, asText(routine.notes), "routine"),
    ),
  ];
  return rows.length
    ? `<div class="list">${rows.slice(0, 3).join("")}</div>`
    : empty("No TODO pins or planner items yet.");
}

function taskMeta(...items: Array<[string, unknown]>): string {
  return items
    .map(([label, value]) => {
      const text = asText(value);
      return text ? `${label}: ${text}` : "";
    })
    .filter(Boolean)
    .join(" / ");
}

function compactRow(title: string, detail: string, badge: string): string {
  return `
    <article class="row compact-row">
      <div><h2>${escapeHtml(title)}</h2><p>${escapeHtml(detail)}</p></div>
      <span class="badge">${escapeHtml(badge || "task")}</span>
    </article>
  `;
}
