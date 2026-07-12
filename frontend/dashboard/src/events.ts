import type { SearchRow } from "./snapshot";

export function dashboardResultClickMetadata(row: SearchRow): Record<string, unknown> {
  return {
    type: row.type,
    href: row.href,
    title_length: row.title.trim().length,
  };
}
