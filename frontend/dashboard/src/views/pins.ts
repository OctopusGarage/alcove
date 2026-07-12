import { pinCard } from "../components/pin-card";
import type { DashboardSnapshot } from "../snapshot";

export function renderPins(snapshot: DashboardSnapshot): string {
  return `
    <header class="page-head">
      <p class="eyebrow">Pinned themes</p>
      <h1>Pins</h1>
      <p>Regular pins are stable references to revisit. TODO pins are themes for future practice, refinement, or deeper study.</p>
      <div class="pin-jumps">
        <button type="button" data-pin-jump="todo">TODO</button>
      </div>
    </header>
    <section id="pin-list" class="pin-list">${snapshot.pins.themes.map((pin) => pinCard(pin)).join("")}</section>
  `;
}
