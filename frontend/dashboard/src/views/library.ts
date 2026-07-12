import { emptyState } from "../components/empty-state";
import { asText, escapeHtml } from "../components/text";
import type { DashboardSnapshot } from "../snapshot";

export function renderLibrary(snapshot: DashboardSnapshot): string {
  const prompts = snapshot.prompts.map((prompt) =>
    row(
      asText(prompt.title),
      [
        asText(prompt.description),
        asText(prompt.content),
        meta("use cases", prompt.use_cases),
        meta("tags", prompt.tags),
      ]
        .filter(Boolean)
        .join("\n"),
      asText(prompt.status) || "prompt",
    ),
  );
  const projects = snapshot.projects.map((project) =>
    row(
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
  return `
    <header class="page-head">
      <p class="eyebrow">Library</p>
      <h1>Prompts and Projects</h1>
      <p>Reusable prompts and project shortcuts for intent routing, kept separate from activity history.</p>
    </header>
    <section class="source-columns">
      <div class="panel"><h2>Prompts</h2>${prompts.join("") || emptyState("No prompts yet.")}</div>
      <div class="panel"><h2>Projects</h2>${projects.join("") || emptyState("No project shortcuts yet.")}</div>
    </section>
  `;
}

function meta(label: string, value: unknown): string {
  if (!Array.isArray(value) || value.length === 0) {
    return "";
  }
  return `${label}: ${value.map((item) => asText(item)).filter(Boolean).join(", ")}`;
}

function row(title: string, detail: string, badge: string): string {
  return `
    <article class="row compact-row">
      <div><h2>${escapeHtml(title)}</h2><p>${escapeHtml(detail)}</p></div>
      <span class="badge">${escapeHtml(badge)}</span>
    </article>
  `;
}
