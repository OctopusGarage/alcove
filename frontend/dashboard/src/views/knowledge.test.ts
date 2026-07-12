import { describe, expect, it } from "vitest";
import type { DashboardSnapshot } from "../snapshot";
import { renderKnowledge } from "./knowledge";

describe("dashboard knowledge view", () => {
  it("keeps source families together with module filtering", () => {
    const html = renderKnowledge({
      knowledge_bases: [{ name: "research", item_count: 3, inbox_count: 1, archive_count: 2 }],
      sources: {
        connectors: [{ id: "github-stars", connector: "github-stars", count: 12 }],
        mounts: [{ name: "archive", type: "directory", count: 34, status: "fresh" }],
      },
    } as unknown as DashboardSnapshot);

    expect(html).toContain("Managed KBs");
    expect(html).toContain("Connectors");
    expect(html).toContain("Mounts");
    expect(html).toContain('data-filter-list');
    expect(html).toContain('data-filter-input');
    expect(html).toContain('data-filter-item');
  });
});
