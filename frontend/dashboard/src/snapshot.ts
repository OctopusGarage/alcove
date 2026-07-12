export const SNAPSHOT_VERSION = 1;

export type PinKind = "regular" | "todo";

export interface ModuleCard {
  id: string;
  title: string;
  subtitle: string;
  href: string;
  metric: number;
  detail: string;
}

export interface ThemePin {
  id: string;
  title: string;
  kind: PinKind;
  summary: string;
  content: string;
  sections: Array<{ heading: string; body: string }>;
  tags: string[];
  priority: string;
  status: string;
  resources: string[];
  source_refs: string[];
  raw_excerpt: string;
  updated_at: string;
}

export interface SearchRow {
  type: string;
  title: string;
  text: string;
  href: string;
}

export interface UsageSummary {
  total_events: number;
  search: {
    total: number;
    zero_result: number;
    zero_result_rate: number;
    surfaces: Record<string, number>;
    types: Record<string, number>;
  };
  dashboard: {
    routes: Record<string, number>;
  };
  actions: {
    total: number;
    areas: Record<string, number>;
    names: Record<string, number>;
  };
  recent: Array<Record<string, unknown>>;
}

export interface HealthSummary {
  status: string;
  issue_count: number;
  totals: Record<string, number>;
  stats: {
    summary_exists: boolean;
    daily_rollups: number;
    updated_at: string;
  };
  data_sources: Array<Record<string, unknown>>;
}

export interface DashboardSnapshot {
  snapshot_version: number;
  generated_at: string;
  home: string;
  summary: {
    title: string;
    subtitle: string;
    counts: Record<string, number>;
  };
  modules: ModuleCard[];
  pins: {
    themes: ThemePin[];
    all: Array<Record<string, unknown>>;
  };
  tasks: {
    pending: Array<Record<string, unknown>>;
    ideas: Array<Record<string, unknown>>;
    routines: Array<Record<string, unknown>>;
    all: Array<Record<string, unknown>>;
    ideas_all: Array<Record<string, unknown>>;
    routines_all: Array<Record<string, unknown>>;
  };
  knowledge_bases: Array<Record<string, unknown>>;
  connectors: Array<Record<string, unknown>>;
  mounts: Array<Record<string, unknown>>;
  radars: Array<Record<string, unknown>>;
  blog_monitor: {
    sources: Array<Record<string, unknown>>;
  };
  sources: {
    connectors: Array<Record<string, unknown>>;
    mounts: Array<Record<string, unknown>>;
    blogs: Array<Record<string, unknown>>;
  };
  prompts: Array<Record<string, unknown>>;
  projects: Array<Record<string, unknown>>;
  activity: Array<Record<string, unknown>>;
  usage: UsageSummary;
  health: HealthSummary;
  search_index: SearchRow[];
}

export function validateSnapshot(value: unknown): DashboardSnapshot {
  if (!isRecord(value)) {
    throw new Error("Snapshot is not an object.");
  }
  if (value.snapshot_version !== SNAPSHOT_VERSION) {
    throw new Error(`Unsupported snapshot version: ${String(value.snapshot_version)}`);
  }
  for (const key of [
    "generated_at",
    "home",
    "summary",
    "modules",
    "pins",
    "usage",
    "health",
    "search_index",
  ]) {
    if (!(key in value)) {
      throw new Error(`Snapshot missing required field: ${key}`);
    }
  }
  if (!Array.isArray(value.modules)) {
    throw new Error("Snapshot modules must be an array.");
  }
  const pins = value.pins;
  if (!isRecord(pins) || !Array.isArray(pins.themes)) {
    throw new Error("Snapshot pins.themes must be an array.");
  }
  return value as unknown as DashboardSnapshot;
}

export async function loadSnapshot(options: { bustCache?: boolean } = {}): Promise<DashboardSnapshot> {
  const path = options.bustCache ? `./snapshot.json?ts=${Date.now()}` : "./snapshot.json";
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Missing snapshot.json. Run `alcove dashboard build` first.");
  }
  return validateSnapshot(await response.json());
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
