import { describe, expect, it } from "vitest";
import type { DashboardSnapshot } from "../snapshot";
import { renderTasks } from "./tasks";

describe("dashboard planner view", () => {
  it("uses stable user-facing planner copy", () => {
    const html = renderTasks({
      tasks: {
        all: [],
        ideas_all: [],
        routines_all: [],
      },
    } as unknown as DashboardSnapshot);

    expect(html).toContain(
      "Shows open tasks, ideas, and routines that need attention, practice, or a follow-up decision.",
    );
    expect(html).toContain('data-filter-list');
    expect(html).toContain('data-filter-input');
    expect(html).toContain('data-filter-limit="12"');
    expect(html).toContain('data-filter-mobile-limit="8"');
    expect(html).toContain('data-filter-chip');
    expect(html).toContain('data-filter-reset="true"');
    expect(html).toContain('data-filter-kind="task"');
    expect(html).toContain('data-filter-query="priority: high"');
    expect(html).toContain('data-filter-query="state: overdue"');
    expect(html).not.toContain("social-radar");
    expect(html).not.toContain("migrated");
  });
});
