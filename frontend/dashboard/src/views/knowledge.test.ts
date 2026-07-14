import { describe, expect, it } from "vitest";
import type { DashboardSnapshot } from "../snapshot";
import { renderKnowledge } from "./knowledge";

describe("dashboard knowledge view", () => {
  it("keeps source families together with module filtering", () => {
    const html = renderKnowledge({
      knowledge_bases: [{ name: "research", item_count: 3, inbox_count: 1, archive_count: 2 }],
      sources: {
        connectors: [{ id: "github-stars", connector: "github-stars", count: 12 }],
        mounts: [
          {
            name: "archive",
            type: "directory",
            count: 5,
            item_count: 34,
            preview_count: 5,
            status: "fresh",
          },
        ],
      },
    } as unknown as DashboardSnapshot);

    expect(html).toContain("Managed KBs");
    expect(html).toContain("3 notes / 1 inbox items / 2 archived items");
    expect(html).toContain("Connectors");
    expect(html).toContain("Mounts");
    expect(html).toContain("34 indexed items / 5 preview items");
    expect(html).not.toContain("5 indexed items");
    expect(html).toContain('data-filter-list');
    expect(html).toContain('data-filter-label="sources"');
    expect(html).toContain('data-filter-input');
    expect(html).toContain('data-filter-item');
  });
});
