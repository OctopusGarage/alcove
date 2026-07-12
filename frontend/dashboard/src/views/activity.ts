import { timeline } from "../components/timeline";
import type { DashboardSnapshot } from "../snapshot";

export function renderActivity(snapshot: DashboardSnapshot): string {
  return `
    <header class="page-head">
      <p class="eyebrow">Activity</p>
      <h1>Recent Activity</h1>
      <p>Shows the Alcove data changes worth scanning: pins, planner, knowledge, prompts, projects, and knowledge-base registry updates. Internal log paths and dashboard refresh noise are excluded.</p>
    </header>
    ${timeline(snapshot.activity)}
  `;
}
