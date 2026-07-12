import { emptyState } from "../components/empty-state";
import { formatSingaporeDateTime } from "../components/date";
import { asText, escapeHtml } from "../components/text";
import type { DashboardSnapshot } from "../snapshot";

export function renderTasks(snapshot: DashboardSnapshot): string {
  const tasks = snapshot.tasks.all.map((task) =>
    row(
      asText(task.display_title) || asText(task.title),
      [
        asText(task.notes),
        meta(
          ["status", task.status],
          ["priority", task.priority],
          ["due", task.due],
          ["state", task.due_state],
          ["overdue", task.overdue_days ? `${asText(task.overdue_days)} days` : ""],
        ),
      ]
        .filter(Boolean)
        .join("\n"),
      asText(task.due_state) || asText(task.status) || "task",
      "task",
    ),
  );
  const ideas = snapshot.tasks.ideas_all.map((idea) =>
    row(
      `Idea: ${asText(idea.title)}`,
      [asText(idea.notes), meta(["status", idea.status], ["created", idea.created_at])]
        .filter(Boolean)
        .join("\n"),
      "idea",
      "idea",
    ),
  );
  const routines = snapshot.tasks.routines_all.map((routine) =>
    row(
      `Routine: ${asText(routine.title)}`,
      [
        asText(routine.notes),
        meta(
          ["status", routine.status],
          ["next", formatSingaporeDateTime(routine.next_due)],
          ["every", `${asText(routine.every_days)} days`],
        ),
      ]
        .filter(Boolean)
        .join("\n"),
      "routine",
      "routine",
    ),
  );
  return `
    <header class="page-head">
      <p class="eyebrow">Personal planning</p>
      <h1>Planner</h1>
      <p>Shows open tasks, ideas, and routines that need attention, practice, or a follow-up decision.</p>
      ${pageJumps([
        ["planner-tasks", "Task List"],
        ["planner-ideas", "Idea Inbox"],
        ["planner-routines", "Routine Templates"],
      ])}
    </header>
    <section class="module-list" data-filter-list data-filter-limit="12" data-filter-mobile-limit="8">
      ${moduleToolbar("Search planner items", [
        ["all", "All"],
        ["task", "Tasks"],
        ["idea", "Ideas"],
        ["routine", "Routines"],
        ["", "High priority", "priority: high"],
        ["", "Overdue", "state: overdue"],
      ])}
      <div class="source-columns" data-filter-items>
        ${panel("Tasks", tasks.join("") || emptyState("No tasks yet."), "planner-tasks")}
        ${panel("Ideas", ideas.join("") || emptyState("No ideas yet."), "planner-ideas")}
        ${panel("Routines", routines.join("") || emptyState("No routines yet."), "planner-routines")}
      </div>
    </section>
  `;
}

function meta(...items: Array<[string, unknown]>): string {
  return items
    .map(([label, value]) => {
      const text = asText(value);
      return text ? `${label}: ${text}` : "";
    })
    .filter(Boolean)
    .join(" / ");
}

function moduleToolbar(label: string, filters: Array<[string, string, string?]> = []): string {
  return `
    <div class="module-toolbar">
      <label>
        <span>${escapeHtml(label)}</span>
        <input class="module-filter-input" type="search" data-filter-input placeholder="Filter this view" />
      </label>
      ${filters.length ? quickFilters(filters) : ""}
      <div class="module-toolbar-actions">
        <span data-filter-count></span>
        <button type="button" data-filter-toggle>Show all</button>
      </div>
    </div>
  `;
}

function quickFilters(filters: Array<[string, string, string?]>): string {
  return `
    <div class="quick-filters" aria-label="Planner quick filters">
      ${filters
        .map(
          ([kind, label, query], index) => `
            <button
              type="button"
              data-filter-chip
              data-filter-kind="${escapeHtml(kind)}"
              data-filter-query="${escapeHtml(query ?? "")}"
              ${index === 0 ? 'data-filter-reset="true"' : ""}
              ${index === 0 ? 'aria-pressed="true"' : 'aria-pressed="false"'}
            >${escapeHtml(label)}</button>
          `,
        )
        .join("")}
    </div>
  `;
}

function pageJumps(items: Array<[string, string]>): string {
  return `
    <div class="page-jumps" aria-label="Planner section jumps">
      ${items.map(([target, label]) => `<button type="button" data-page-jump="${escapeHtml(target)}">${escapeHtml(label)}</button>`).join("")}
    </div>
  `;
}

function panel(title: string, content: string, id: string): string {
  return `<div id="${escapeHtml(id)}" class="panel jump-panel" tabindex="-1"><h2>${escapeHtml(title)}</h2>${content}</div>`;
}

function row(title: string, detail: string, badge: string, kind: string): string {
  const filterText = [title, detail, badge, kind].filter(Boolean).join(" ");
  return `
    <article class="row" data-filter-item data-kind="${escapeHtml(kind)}" data-filter-text="${escapeHtml(filterText)}">
      <div><h2>${escapeHtml(title)}</h2><p>${escapeHtml(detail)}</p></div>
      <span class="badge">${escapeHtml(badge || "task")}</span>
    </article>
  `;
}
