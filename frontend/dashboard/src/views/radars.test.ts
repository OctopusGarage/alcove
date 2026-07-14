import { describe, expect, it } from "vitest";
import type { DashboardSnapshot } from "../snapshot";
import { renderRadars } from "./radars";

describe("dashboard radars view", () => {
  it("renders an empty state when dynamic snapshots omit radars", () => {
    const html = renderRadars({ radars: null } as unknown as DashboardSnapshot);

    expect(html).toContain("Information Radars");
    expect(html).toContain("No radars configured yet.");
    expect(html).toContain('data-filter-list');
    expect(html).toContain('data-filter-label="radars"');
  });

  it("uses radar run_at as the latest run timestamp", () => {
    const html = renderRadars({
      radars: [
        {
          id: "tech-news",
          name: "Tech News",
          status: "current",
          schedule_enabled: true,
          source_count: 7,
          tags: ["technology"],
          last_run: {
            status: "completed",
            run_at: "2026-07-12T16:11:35+00:00",
          },
        },
      ],
    } as unknown as DashboardSnapshot);

    expect(html).toContain("Tech News");
    expect(html).toContain("Jul 13, 2026, 00:11 SGT");
    expect(html).not.toContain("No runs yet");
  });
});
