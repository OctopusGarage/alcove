import type { DashboardSnapshot } from "./snapshot";
import { renderActivity } from "./views/activity";
import { renderHome } from "./views/home";
import { renderKnowledge } from "./views/knowledge";
import { renderLibrary } from "./views/library";
import { renderPins } from "./views/pins";
import { renderTasks } from "./views/tasks";
import { renderUsage } from "./views/usage";

export type Route =
  | "/"
  | "/pins"
  | "/knowledge"
  | "/planner"
  | "/library"
  | "/activity"
  | "/usage";

export const routes: Array<{ path: Route; label: string; description: string }> = [
  { path: "/", label: "Home", description: "Daily status and module map" },
  { path: "/pins", label: "Pins", description: "Stable references and themes to revisit" },
  { path: "/knowledge", label: "Knowledge", description: "Managed KBs, mounts, connectors" },
  { path: "/planner", label: "Planner", description: "Tasks, ideas, routines" },
  { path: "/library", label: "Library", description: "Prompts and project shortcuts" },
  { path: "/activity", label: "Activity", description: "Usage trail and file changes" },
  { path: "/usage", label: "Usage", description: "Search health and entry points" },
];

export function currentRoute(): Route {
  const value = window.location.hash.replace(/^#/, "") || "/";
  if (value === "/tasks") {
    return "/planner";
  }
  if (value === "/sources") {
    return "/knowledge";
  }
  if (routes.some((route) => route.path === value)) {
    return value as Route;
  }
  return "/";
}

export function navigate(path: string): void {
  window.location.hash = path;
}

export function renderRoute(snapshot: DashboardSnapshot, route: Route): string {
  if (route === "/pins") {
    return renderPins(snapshot);
  }
  if (route === "/knowledge") {
    return renderKnowledge(snapshot);
  }
  if (route === "/planner") {
    return renderTasks(snapshot);
  }
  if (route === "/library") {
    return renderLibrary(snapshot);
  }
  if (route === "/activity") {
    return renderActivity(snapshot);
  }
  if (route === "/usage") {
    return renderUsage(snapshot);
  }
  return renderHome(snapshot);
}
