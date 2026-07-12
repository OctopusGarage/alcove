import type { DashboardSnapshot, SearchRow } from "./snapshot";

export interface SearchResult extends SearchRow {
  score: number;
}

export function searchSnapshot(snapshot: DashboardSnapshot, query: string): SearchResult[] {
  const q = query.trim().toLowerCase();
  if (!q) {
    return [];
  }
  return snapshot.search_index
    .map((row) => ({ ...row, score: scoreRow(row, q) }))
    .filter((row) => row.score > 0)
    .sort((a, b) => b.score - a.score || a.title.localeCompare(b.title));
}

function scoreRow(row: SearchRow, query: string): number {
  let score = 0;
  if (row.title.toLowerCase().includes(query)) {
    score += 5;
  }
  if (row.text.toLowerCase().includes(query)) {
    score += 1;
  }
  return score;
}
