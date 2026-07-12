import { formatSingaporeDateTime } from "./date";
import { asText, escapeHtml } from "./text";

interface TimelineOptions {
  limit?: number;
  compact?: boolean;
}

export function timeline(
  items: Array<Record<string, unknown>>,
  options: TimelineOptions = {},
): string {
  if (items.length === 0) {
    return `<div class="empty">No activity yet. This will fill in as Alcove commands run.</div>`;
  }
  const limit = options.limit ?? 20;
  return `
    <div class="timeline${options.compact ? " compact-timeline" : ""}">
      ${items
        .slice(0, limit)
        .map(
          (item) => `
            <article>
              <span>${escapeHtml(asText(item.area) || "alcove")}</span>
              <h3>${escapeHtml(asText(item.name) || asText(item.action) || "Activity")}</h3>
              <p>${escapeHtml(formatSingaporeDateTime(item.updated_at))}</p>
              ${
                !options.compact && asText(item.detail)
                  ? `<p class="activity-detail">${escapeHtml(asText(item.detail))}</p>`
                  : ""
              }
            </article>`,
        )
        .join("")}
    </div>
  `;
}
