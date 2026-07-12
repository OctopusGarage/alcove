import { describe, expect, it } from "vitest";
import type { DashboardSnapshot } from "../snapshot";
import { renderRadars } from "./radars";

describe("dashboard radars view", () => {
  it("renders an empty state when dynamic snapshots omit radars", () => {
    const html = renderRadars({ radars: null } as unknown as DashboardSnapshot);

    expect(html).toContain("Information Radars");
    expect(html).toContain("No radars configured yet.");
    expect(html).toContain('data-filter-list');
  });
});
