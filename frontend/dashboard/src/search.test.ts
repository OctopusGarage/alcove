import { describe, expect, it } from "vitest";
import { searchSnapshot } from "./search";
import type { DashboardSnapshot } from "./snapshot";

describe("dashboard search", () => {
  it("ranks title matches above body matches", () => {
    const snapshot = {
      search_index: [
        { type: "pin", title: "Workflow", text: "agent loop", href: "/pins" },
        { type: "pin", title: "Agent", text: "workflow design", href: "/pins" },
      ],
    } as DashboardSnapshot;

    const results = searchSnapshot(snapshot, "workflow");

    expect(results.map((row) => row.title)).toEqual(["Workflow", "Agent"]);
  });
});
