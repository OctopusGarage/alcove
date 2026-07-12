import { describe, expect, it } from "vitest";
import type { DashboardSnapshot, ThemePin } from "../snapshot";
import { renderHome } from "./home";

describe("dashboard home", () => {
  it("labels planner fallback as a planner queue instead of practice themes", () => {
    const html = renderHome(
      snapshot({
        todoPins: [],
        pendingTasks: [{ title: "Review inbox", notes: "Summarize pending posts." }],
      }),
    );

    expect(html).toContain("Planner Queue");
    expect(html).toContain("Open planner");
    expect(html).not.toContain("Themes to Practice");
  });

  it("uses precise ledger labels for searchable data and source families", () => {
    const html = renderHome(
      snapshot({
        todoPins: [pin("todo-pin", "Try Later", "todo")],
        pendingTasks: [],
      }),
    );

    expect(html).toContain("TODO Pins");
    expect(html).toContain("Pin Records");
    expect(html).toContain("1 featured theme pins");
    expect(html).toContain("Searchable");
    expect(html).toContain("indexed records");
    expect(html).toContain("Source Coverage");
    expect(html).toContain("5 types");
    expect(html).toContain("Managed KBs: 1; Mounts: 1; Connectors: 3");
    expect(html).not.toContain("Indexed");
    expect(html).not.toContain("Themes to Practice");
  });

  it("leads with pin records on the home ledger without rendering empty theme panels", () => {
    const html = renderHome(
      snapshot({
        todoPins: [],
        pendingTasks: [],
        totalPins: 19,
      }),
    );

    expect(html).toContain("Pin Records");
    expect(html).toContain(">19</b>");
    expect(html).toContain("0 featured theme pins");
    expect(html).not.toContain("Regular Theme Pins");
  });
});

function snapshot(input: {
  todoPins: ThemePin[];
  pendingTasks: Array<Record<string, unknown>>;
  totalPins?: number;
}): DashboardSnapshot {
  return {
    snapshot_version: 1,
    generated_at: "2026-07-11T00:00:00+08:00",
    home: "Alcove Home",
    summary: {
      title: "Alcove Dashboard",
      subtitle: "Local-first personal knowledge workbench",
      counts: {
        theme_pins: input.todoPins.length,
        pins: input.totalPins ?? input.todoPins.length,
        pending_tasks: input.pendingTasks.length,
        knowledge_items: 6,
        mount_items: 1,
        connector_items: 3,
        knowledge_bases: 1,
        mounts: 1,
        connectors: 3,
      },
    },
    modules: [],
    pins: {
      themes: input.todoPins,
      all: input.todoPins.map((item) => ({ ...item })),
    },
    tasks: {
      pending: input.pendingTasks,
      ideas: [],
      routines: [],
      all: input.pendingTasks,
      ideas_all: [],
      routines_all: [],
    },
    knowledge_bases: [],
    connectors: [],
    mounts: [],
    radars: [],
    blog_monitor: { sources: [] },
    sources: { connectors: [], mounts: [], blogs: [] },
    prompts: [],
    projects: [],
    activity: [],
    usage: {
      total_events: 0,
      search: {
        total: 0,
        zero_result: 0,
        zero_result_rate: 0,
        surfaces: {},
        types: {},
      },
      dashboard: { routes: {} },
      actions: { total: 0, areas: {}, names: {} },
      recent: [],
    },
    health: {
      status: "ok",
      issue_count: 0,
      totals: {},
      stats: { summary_exists: true, daily_rollups: 0, updated_at: "" },
      data_sources: [],
    },
    search_index: [],
  };
}

function pin(id: string, title: string, kind: "regular" | "todo"): ThemePin {
  return {
    id,
    title,
    kind,
    summary: "Pin summary.",
    content: "Pin content.",
    sections: [],
    tags: [],
    priority: "medium",
    status: "active",
    resources: [],
    source_refs: [],
    raw_excerpt: "Pin summary.",
    updated_at: "2026-07-11T00:00:00+08:00",
  };
}
