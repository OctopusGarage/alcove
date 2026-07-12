import type { ModuleCard } from "../snapshot";
import { escapeHtml } from "./text";

export function moduleCard(module: ModuleCard): string {
  return `
    <a class="module-card" href="#${escapeHtml(module.href)}">
      <span>${escapeHtml(module.id)}</span>
      <strong>${escapeHtml(module.metric)}</strong>
      <h2>${escapeHtml(module.title)}</h2>
      <p>${escapeHtml(module.detail)}</p>
    </a>
  `;
}
