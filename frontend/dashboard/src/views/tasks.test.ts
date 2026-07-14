import { describe, expect, it } from "vitest";
import type { DashboardSnapshot } from "../snapshot";
import { renderTasks } from "./tasks";

describe("dashboard planner view", () => {
  it("uses stable user-facing planner copy", () => {
    const html = renderTasks({
      tasks: {
        pending: [],
        ideas: [],
        routines: [],
        all: [],
        ideas_all: [],
        routines_all: [{ title: "Archived routine", status: "archived" }],
      },
    } as unknown as DashboardSnapshot);

    expect(html).toContain(
      "Shows open tasks, ideas, and routines that need attention, practice, or a follow-up decision.",
    );
    expect(html).toContain('data-filter-list');
    expect(html).toContain('data-filter-label="planner items"');
    expect(html).toContain('data-filter-input');
    expect(html).toContain('data-filter-limit="all"');
    expect(html).toContain('data-filter-mobile-limit="all"');
    expect(html).toContain('data-filter-chip');
    expect(html).toContain('data-filter-reset="true"');
    expect(html).not.toContain('data-filter-kind="all"');
    expect(html).toContain('data-filter-kind="task"');
    expect(html).toContain('data-filter-query="priority: high"');
    expect(html).toContain('data-filter-query="state: overdue"');
    expect(html).toContain("No routines yet.");
    expect(html).not.toContain("Archived routine");
    expect(html).not.toContain("social-radar");
    expect(html).not.toContain("migrated");
  });

  it("does not cap planner rows before routines are visible", () => {
    const html = renderTasks({
      tasks: {
        pending: Array.from({ length: 5 }, (_, index) => ({
          title: `Task ${index + 1}`,
          status: "pending",
        })),
        ideas: Array.from({ length: 7 }, (_, index) => ({
          title: `Idea ${index + 1}`,
          status: "active",
        })),
        routines: [
          { title: "Weekly review", status: "active", every_days: 7 },
          { title: "Monthly review", status: "active", every_days: 30 },
        ],
        all: [],
        ideas_all: [],
        routines_all: [],
      },
    } as unknown as DashboardSnapshot);

    expect(html).toContain("Routine: Weekly review");
    expect(html).toContain("Routine: Monthly review");
    expect(html).toContain('data-filter-limit="all"');
  });
});
