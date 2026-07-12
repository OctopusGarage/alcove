import "./styles/tokens.css";
import "./styles/layout.css";
import "./styles/views.css";
import { layout } from "./components/layout";
import { currentRoute, renderRoute } from "./router";
import { dashboardResultClickMetadata } from "./events";
import { searchSnapshot } from "./search";
import { loadSnapshot, type DashboardSnapshot } from "./snapshot";
import { escapeHtml } from "./components/text";
import { formatSingaporeDateTime } from "./components/date";

const app = document.querySelector<HTMLDivElement>("#app");

if (!app) {
  throw new Error("Missing #app root.");
}
const root = app;

let snapshot: DashboardSnapshot | null = null;
let snapshotFingerprint = "";
let searchEventTimer: number | undefined;

loadSnapshot()
  .then((loaded) => {
    snapshot = loaded;
    snapshotFingerprint = fingerprint(loaded);
    render();
    startAutoRefresh();
  })
  .catch((error: unknown) => {
    root.innerHTML = `
      <main class="fatal">
        <p class="eyebrow">Dashboard unavailable</p>
        <h1>Snapshot missing</h1>
        <p>${escapeHtml(error instanceof Error ? error.message : String(error))}</p>
        <code>alcove dashboard --home ~/.alcove build</code>
      </main>
    `;
  });

window.addEventListener("hashchange", () => {
  render();
  recordDashboardEvent("dashboard.route", "Dashboard route viewed", {
    route: currentRoute(),
  });
});

function render(): void {
  if (!snapshot) {
    return;
  }
  root.innerHTML = `<div class="shell">${layout(snapshot, renderRoute(snapshot, currentRoute()))}</div>`;
  bindSearch(snapshot);
  bindModuleFilters();
  bindPinJumps();
  bindCommandCopy();
}

function bindSearch(current: DashboardSnapshot): void {
  const input = document.querySelector<HTMLInputElement>("#global-search");
  const target = document.querySelector<HTMLDivElement>("#search-results");
  if (!input || !target) {
    return;
  }
  input.addEventListener("input", () => {
    const results = searchSnapshot(current, input.value).slice(0, 8);
    target.innerHTML = results.length
      ? results
          .map(
            (row, index) => `
              <a href="#${escapeHtml(row.href)}" data-search-result="${index}">
                <span>${escapeHtml(row.type)}</span>
                <b>${escapeHtml(row.title)}</b>
              </a>`,
          )
          .join("")
      : input.value.trim()
        ? '<div class="empty small">No matching result in this snapshot.</div>'
        : "";
    if (input.value.trim().length >= 2) {
      window.clearTimeout(searchEventTimer);
      searchEventTimer = window.setTimeout(() => {
        recordDashboardEvent("dashboard.search", "Dashboard search used", {
          query_length: input.value.trim().length,
          result_count: results.length,
        });
      }, 700);
    }
    target.querySelectorAll<HTMLAnchorElement>("[data-search-result]").forEach((anchor) => {
      anchor.addEventListener("click", () => {
        const index = Number(anchor.dataset.searchResult ?? "-1");
        const row = results[index];
        if (!row) {
          return;
        }
        recordDashboardEvent(
          "dashboard.result_open",
          "Dashboard search result opened",
          dashboardResultClickMetadata(row),
        );
      });
    });
  });
}

function bindModuleFilters(): void {
  document.querySelectorAll<HTMLElement>("[data-filter-list]").forEach((container) => {
    const input = container.querySelector<HTMLInputElement>("[data-filter-input]");
    const count = container.querySelector<HTMLElement>("[data-filter-count]");
    const toggle = container.querySelector<HTMLButtonElement>("[data-filter-toggle]");
    const chips = Array.from(container.querySelectorAll<HTMLButtonElement>("[data-filter-chip]"));
    const items = Array.from(container.querySelectorAll<HTMLElement>("[data-filter-item]"));
    const desktopLimit = Number(container.dataset.filterLimit ?? "24");
    const mobileLimit = Number(container.dataset.filterMobileLimit ?? desktopLimit);
    let expanded = false;
    let activeKind = "";
    let activeChipQuery = "";

    const apply = (): void => {
      const limit = window.matchMedia("(max-width: 560px)").matches ? mobileLimit : desktopLimit;
      const typedQuery = (input?.value ?? "").trim().toLowerCase();
      const chipQuery = activeChipQuery.trim().toLowerCase();
      const matched = items.filter((item) => {
        const text = (item.dataset.filterText ?? item.innerText).toLowerCase();
        const kindMatches = !activeKind || item.dataset.kind === activeKind;
        const typedMatches = !typedQuery || text.includes(typedQuery);
        const chipMatches = !chipQuery || text.includes(chipQuery);
        return kindMatches && typedMatches && chipMatches;
      });
      let visible = 0;
      items.forEach((item) => {
        const matches = matched.includes(item);
        const withinLimit = expanded || typedQuery.length > 0 || chipQuery.length > 0 || visible < limit;
        item.hidden = !matches || !withinLimit;
        if (matches && withinLimit) {
          visible += 1;
        }
      });
      if (count) {
        count.textContent = `${visible} of ${matched.length} shown`;
      }
      if (toggle) {
        toggle.hidden = matched.length <= limit || typedQuery.length > 0 || chipQuery.length > 0;
        toggle.textContent = expanded ? "Limit view" : `Show all ${matched.length}`;
      }
    };

    input?.addEventListener("input", apply);
    chips.forEach((chip) => {
      chip.addEventListener("click", () => {
        activeKind = chip.dataset.filterKind ?? "";
        activeChipQuery = chip.dataset.filterQuery ?? "";
        if (chip.dataset.filterReset === "true" && input) {
          input.value = "";
        }
        expanded = false;
        chips.forEach((item) => {
          item.setAttribute("aria-pressed", item === chip ? "true" : "false");
        });
        apply();
      });
    });
    toggle?.addEventListener("click", () => {
      expanded = !expanded;
      apply();
    });
    apply();
  });
}

function bindPinJumps(): void {
  document.querySelectorAll<HTMLButtonElement>("[data-pin-jump]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.querySelector<HTMLElement>(
        `#pin-${button.dataset.pinJump ?? ""}`,
      );
      if (!target) {
        return;
      }
      target.scrollIntoView({ behavior: "auto", block: "start" });
      target.focus({ preventScroll: true });
    });
  });
}

function bindCommandCopy(): void {
  document.querySelectorAll<HTMLButtonElement>("[data-copy-command]").forEach((button) => {
    button.addEventListener("click", () => {
      const command = button.dataset.copyCommand ?? "";
      if (!command) {
        return;
      }
      const clipboard = navigator.clipboard;
      if (!clipboard) {
        return;
      }
      clipboard
        .writeText(command)
        .then(() => {
          button.textContent = "Copied";
          window.setTimeout(() => {
            button.textContent = command;
          }, 1200);
        })
        .catch(() => {
          button.textContent = command;
        });
    });
  });
}

function startAutoRefresh(): void {
  window.setInterval(() => {
    if (document.hidden) {
      return;
    }
    loadSnapshot()
      .then((next) => {
        const nextFingerprint = fingerprint(next);
        if (nextFingerprint === snapshotFingerprint) {
          snapshot = next;
          updateSnapshotMeta(next);
          return;
        }
        snapshot = next;
        snapshotFingerprint = nextFingerprint;
        render();
      })
      .catch(() => {
        // Keep the last good snapshot visible.
      });
  }, 20_000);
}

function updateSnapshotMeta(current: DashboardSnapshot): void {
  const generatedAt = document.querySelector<HTMLElement>("[data-snapshot-generated-at]");
  const home = document.querySelector<HTMLElement>("[data-snapshot-home]");
  if (generatedAt) {
    generatedAt.textContent = formatSingaporeDateTime(current.generated_at, { seconds: true });
  }
  if (home) {
    home.textContent = current.home;
  }
}

function fingerprint(current: DashboardSnapshot): string {
  return JSON.stringify({
    counts: current.summary.counts,
    pins: current.pins.themes.map((pin) => [pin.id, pin.updated_at]),
    tasks: current.tasks.pending.length,
    activity: current.activity.slice(0, 8).map((item) => [
      item.name,
      item.detail,
      item.updated_at,
    ]),
  });
}

function recordDashboardEvent(
  action: string,
  summary: string,
  metadata: Record<string, unknown>,
): void {
  if (window.location.protocol !== "http:" && window.location.protocol !== "https:") {
    return;
  }
  fetch("./events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, summary, metadata }),
    keepalive: true,
  }).catch(() => {
    // Analytics must never affect the dashboard interaction.
  });
}
