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
        activeIdeas: [{ title: "Improve dashboard" }, { title: "Review OKF" }],
        activeRoutines: [{ title: "Weekly review" }],
      }),
    );

    expect(html).toContain("TODO Pins");
    expect(html).toContain("Pin Collections");
    expect(html).toContain("0 regular collections / 1 TODO collection");
    expect(html).toContain("Planner Items");
    expect(html).toContain(">3</b>");
    expect(html).toContain("0 pending tasks / 2 ideas / 1 routine");
    expect(html).toContain("Searchable");
    expect(html).toContain("indexed records");
    expect(html).toContain("Source Coverage");
    expect(html).toContain("5 sources");
    expect(html).toContain("Managed KBs: 1; Mounts: 1; Connectors: 3");
    expect(html).not.toContain("Indexed");
    expect(html).not.toContain("Themes to Practice");
  });

  it("leads with pin collections on the home ledger without rendering empty theme panels", () => {
    const html = renderHome(
      snapshot({
        todoPins: [],
        pendingTasks: [],
      }),
    );

    expect(html).toContain("Pin Collections");
    expect(html).toContain(">0</b>");
    expect(html).toContain("0 regular collections / 0 TODO collections");
    expect(html).not.toContain("Regular Theme Pins");
  });
});

function snapshot(input: {
  todoPins: ThemePin[];
  pendingTasks: Array<Record<string, unknown>>;
  activeIdeas?: Array<Record<string, unknown>>;
  activeRoutines?: Array<Record<string, unknown>>;
  totalPins?: number;
}): DashboardSnapshot {
  const activeIdeas = input.activeIdeas ?? [];
  const activeRoutines = input.activeRoutines ?? [];
  return {
    snapshot_version: 1,
    generated_at: "2026-07-11T00:00:00+08:00",
    home: "Alcove Home",
    summary: {
      title: "Alcove Dashboard",
      subtitle: "Local-first personal knowledge workbench",
      counts: {
        theme_pins: input.todoPins.length,
        pin_collections: input.todoPins.length,
        regular_theme_pins: input.todoPins.filter((pin) => pin.kind === "regular").length,
        todo_theme_pins: input.todoPins.filter((pin) => pin.kind === "todo").length,
        pins: input.totalPins ?? input.todoPins.length,
        pending_tasks: input.pendingTasks.length,
        active_ideas: activeIdeas.length,
        active_routines: activeRoutines.length,
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
      ideas: activeIdeas,
      routines: activeRoutines,
      all: input.pendingTasks,
      ideas_all: activeIdeas,
      routines_all: activeRoutines,
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
