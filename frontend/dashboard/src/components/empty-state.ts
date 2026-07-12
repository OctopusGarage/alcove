import { escapeHtml } from "./text";

export function emptyState(message: string): string {
  return `<div class="empty">${escapeHtml(message)}</div>`;
}
