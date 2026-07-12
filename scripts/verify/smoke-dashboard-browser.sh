#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

root="${ALCOVE_DASHBOARD_BROWSER_DIR:-$repo_root/.tmp/dashboard-browser}"
home="$root/home"
kb="$root/kb"
fixtures="$root/fixtures"
report="$root/dashboard-browser-report.json"

run() {
  printf 'dashboard-browser: %s\n' "$*" >&2
  "$@"
}

alcove() {
  run uv run alcove "$@"
}

rm -rf "$root"
mkdir -p "$fixtures"

export ALCOVE_HOME="$home"
alcove home init --json > "$fixtures/home-init.json"
alcove init "$kb" > "$fixtures/kb-init.txt"
alcove kb add dashboard_kb "$kb" --json > "$fixtures/kb-add.json"
alcove pin --home "$home" add "Dashboard Browser Pin" \
  --summary "Browser smoke pin." \
  --content "Dashboard browser search needle." \
  --kind regular \
  --tag dashboard \
  --json > "$fixtures/pin-add.json"
alcove prompt --home "$home" save "Dashboard Browser Prompt" \
  --description "Browser smoke prompt." \
  --content "Use dashboard browser smoke." \
  --tag dashboard \
  --json > "$fixtures/prompt-save.json"
alcove task --home "$home" add "Dashboard Browser Task" \
  --notes "Browser smoke task." \
  --priority high \
  --due 2026-07-10 \
  --tag dashboard \
  --json > "$fixtures/task-add.json"
alcove knowledge --kb dashboard_kb add-note dashboard/browser "Dashboard Browser Concept" \
  --summary "Dashboard browser concept." \
  --tag dashboard > "$fixtures/knowledge-add.json"

run uv run python - "$home" "$kb" <<'PY'
from pathlib import Path
import sys

from alcove.home import AlcoveHome
from alcove.knowledge import AddConceptRequest, KnowledgeModule
from alcove.pins import AddPinRequest, PinsModule
from alcove.projects import AddProjectRequest, ProjectsModule
from alcove.prompts import AddPromptRequest, PromptsModule
from alcove.tasks import AddIdeaRequest, AddRoutineRequest, AddTaskRequest, TasksModule
from alcove.workspace import Workspace

home = AlcoveHome.init(Path(sys.argv[1]))
workspace = Workspace.discover(Path(sys.argv[2]))

pins = PinsModule(home=home)
prompts = PromptsModule(home=home)
tasks = TasksModule(home=home)
projects = ProjectsModule(home=home)
knowledge = KnowledgeModule(workspace)

for index in range(80):
    pins.add(
        AddPinRequest(
            title=f"Dashboard Dense Pin {index:02d}",
            summary=f"Dense pin summary {index:02d}.",
            content=(
                f"Dense dashboard pin body {index:02d}. "
                "This exercises card density, search, and repeated review."
            ),
            kind="todo" if index % 4 == 0 else "regular",
            tags=["dashboard", "dense"],
        )
    )

for index in range(30):
    prompts.save(
        AddPromptRequest(
            title=f"Dashboard Dense Prompt {index:02d}",
            description=f"Dense prompt description {index:02d}.",
            content=f"Use this dense dashboard prompt fixture {index:02d}.",
            use_cases=["dashboard-density"],
            tags=["dashboard", "dense"],
        )
    )

for index in range(50):
    tasks.task_add(
        AddTaskRequest(
            title=f"Dashboard Dense Task {index:02d}",
            notes=f"Dense task notes {index:02d}.",
            tags=["dashboard", "dense"],
            priority="high" if index % 5 == 0 else "medium",
        )
    )

for index in range(12):
    tasks.idea_add(
        AddIdeaRequest(
            title=f"Dashboard Dense Idea {index:02d}",
            notes=f"Dense idea notes {index:02d}.",
            tags=["dashboard", "dense"],
        )
    )
    tasks.routine_add(
        AddRoutineRequest(
            title=f"Dashboard Dense Routine {index:02d}",
            notes=f"Dense routine notes {index:02d}.",
            tags=["dashboard", "dense"],
            every_days=7,
            next_due="2026-07-10",
        )
    )

for index in range(160):
    knowledge.add_concept(
        AddConceptRequest(
            topic="dashboard/browser",
            title=f"Dashboard Dense Knowledge {index:02d}",
            summary=(
                f"Dense dashboard knowledge note {index:02d}. "
                "This fixture validates large search indexes and dashboard density."
            ),
            tags=["dashboard", "dense"],
        )
    )

for index in range(10):
    project_dir = Path(sys.argv[2]).parent / f"dense-project-{index:02d}"
    project_dir.mkdir(parents=True, exist_ok=True)
    projects.add(
        AddProjectRequest(
            alias=f"dense-project-{index:02d}",
            path=str(project_dir),
            note=f"Dense dashboard project shortcut {index:02d}.",
        )
    )
PY
alcove dashboard --home "$home" build --json > "$fixtures/dashboard-build.json"

run python3 - "$home/dashboard" "$root/screenshots" "$report" <<'PY'
from __future__ import annotations

from contextlib import contextmanager
import http.server
import json
from pathlib import Path
import socketserver
import sys
import threading
from typing import Any

try:
    from playwright.sync_api import sync_playwright
except Exception as exc:  # pragma: no cover - depends on machine setup
    report = Path(sys.argv[3])
    report.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "skipped",
        "reason": f"python playwright is not available: {exc}",
        "checks": [],
    }
    report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(0)

dashboard_root = Path(sys.argv[1]).resolve()
screenshots = Path(sys.argv[2])
report = Path(sys.argv[3])
screenshots.mkdir(parents=True, exist_ok=True)
snapshot = json.loads((dashboard_root / "snapshot.json").read_text(encoding="utf-8"))


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    def do_POST(self) -> None:  # noqa: N802
        if self.path.endswith("/events"):
            self.send_response(204)
            self.end_headers()
            return
        self.send_error(404)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


@contextmanager
def serve(root: Path):
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(root), **kwargs)
    server = Server(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "status": "passed" if ok else "failed", "detail": detail})


def visual_summary(page: Any, *, viewport: str, route: str) -> dict[str, Any]:
    return page.evaluate(
        """({ viewport, route }) => {
            const main = document.querySelector('main') || document.body;
            const text = (main.innerText || '').replace(/\\s+/g, ' ').trim();
            const headings = Array.from(main.querySelectorAll('h1,h2,h3'))
              .map((node) => (node.textContent || '').replace(/\\s+/g, ' ').trim())
              .filter(Boolean)
              .slice(0, 8);
            const regions = Array.from(main.querySelectorAll('section, article, details'))
              .filter((node) => node.getBoundingClientRect().height > 20);
            const visibleRegions = regions.filter((node) => {
              const rect = node.getBoundingClientRect();
              return rect.bottom > 0 && rect.top < window.innerHeight;
            });
            const maxRegionHeight = regions.reduce((max, node) => {
              const rect = node.getBoundingClientRect();
              return Math.max(max, Math.round(rect.height));
            }, 0);
            return {
              viewport,
              route,
              headings,
              first_screen_excerpt: text.slice(0, 360),
              text_length: text.length,
              region_count: regions.length,
              visible_region_count: visibleRegions.length,
              max_region_height: maxRegionHeight,
              interactive_controls: main.querySelectorAll('a, button, input, summary').length,
              search_present: Boolean(main.querySelector('#global-search, [data-filter-input]')),
              module_filter_present: Boolean(main.querySelector('[data-filter-list] [data-filter-input]')),
              document_width: document.documentElement.scrollWidth,
              viewport_width: document.documentElement.clientWidth,
              document_height: document.documentElement.scrollHeight,
              viewport_height: document.documentElement.clientHeight,
              horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
            };
        }""",
        {"viewport": viewport, "route": route},
    )


checks: list[dict[str, Any]] = []
console_errors: list[str] = []
visual_summaries: list[dict[str, Any]] = []
viewports = [
    ("desktop", 1440, 1000),
    ("mobile", 390, 844),
]
routes = ["/", "/pins", "/knowledge", "/planner", "/library", "/activity", "/usage"]
large_dataset = {
    "pins": snapshot["summary"]["counts"]["pins"],
    "tasks_total": snapshot["summary"]["counts"]["tasks_total"],
    "ideas_total": snapshot["summary"]["counts"]["ideas_total"],
    "routines_total": snapshot["summary"]["counts"]["routines_total"],
    "prompts": snapshot["summary"]["counts"]["prompts"],
    "projects": snapshot["summary"]["counts"]["projects"],
    "knowledge_items": snapshot["summary"]["counts"]["knowledge_items"],
    "search_index_items": len(snapshot["search_index"]),
}

with serve(dashboard_root) as base_url:
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:  # pragma: no cover - depends on browser install
            payload = {
                "status": "skipped",
                "reason": f"playwright browser is not available: {exc}",
                "checks": checks,
            }
            report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            raise SystemExit(0)

        for label, width, height in viewports:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.goto(base_url, wait_until="networkidle")
            add_check(checks, f"{label}_title", "Alcove" in page.locator("body").inner_text())
            page.screenshot(path=str(screenshots / f"{label}-home.png"), full_page=True)
            add_check(
                checks,
                f"{label}_screenshot",
                (screenshots / f"{label}-home.png").stat().st_size > 0,
                str(screenshots / f"{label}-home.png"),
            )
            for route in routes:
                page.goto(f"{base_url}#{route}", wait_until="networkidle")
                body = page.locator("body").inner_text()
                add_check(checks, f"{label}_route_{route or 'home'}", len(body.strip()) > 100, route)
                no_horizontal_overflow = page.evaluate(
                    "() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1"
                )
                add_check(
                    checks,
                    f"{label}_no_horizontal_overflow_{route or 'home'}",
                    bool(no_horizontal_overflow),
                    route,
                )
                if route == "/usage":
                    body_lower = body.lower()
                    add_check(
                        checks,
                        f"{label}_usage_health",
                        ("数据健康" in body or "data health" in body_lower)
                        and "data sources" in body_lower,
                        body[:300],
                    )
                    diagnostic_summary = (
                        page.locator("details.diagnostic-action summary").first.inner_text().lower()
                    )
                    add_check(
                        checks,
                        f"{label}_usage_health_diagnostic_action",
                        diagnostic_summary in {"诊断命令", "diagnostic command"},
                        body[:500],
                    )
                    add_check(
                        checks,
                        f"{label}_usage_health_copy_command",
                        page.locator(
                            "details.diagnostic-action button[data-copy-command='alcove validate --kb dashboard_kb --json']"
                        ).count()
                        == 1,
                        body[:500],
                    )
                if route == "/planner":
                    visual_summaries.append(
                        visual_summary(page, viewport=label, route=route)
                    )
                    planner_filter = page.locator("[data-filter-input]").first
                    add_check(
                        checks,
                        f"{label}_planner_module_filter",
                        planner_filter.count() == 1,
                        body[:300],
                    )
                    expected_initial_count = "8 OF 75 SHOWN" if label == "mobile" else "12 OF 75 SHOWN"
                    initial_planner_body = page.locator("main").inner_text()
                    add_check(
                        checks,
                        f"{label}_planner_semantic_items",
                        "Dashboard Dense Task 00" in initial_planner_body
                        and "SEARCH PLANNER ITEMS" in initial_planner_body
                        and expected_initial_count in initial_planner_body,
                        initial_planner_body[:500],
                    )
                    planner_filter.fill("Dashboard Dense Task 41")
                    page.wait_for_timeout(200)
                    filtered_body = page.locator("main").inner_text()
                    add_check(
                        checks,
                        f"{label}_planner_filter_finds_collapsed_item",
                        "Dashboard Dense Task 41" in filtered_body
                        and "Dashboard Dense Task 00" not in filtered_body,
                        filtered_body[:400],
                    )
                    planner_filter.fill("Dashboard Dense Idea 00")
                    page.wait_for_timeout(200)
                    idea_filtered_body = page.locator("main").inner_text()
                    add_check(
                        checks,
                        f"{label}_planner_filter_finds_idea",
                        "Dashboard Dense Idea 00" in idea_filtered_body,
                        idea_filtered_body[:300],
                    )
                    planner_filter.fill("Dashboard Dense Routine 00")
                    page.wait_for_timeout(200)
                    routine_filtered_body = page.locator("main").inner_text()
                    add_check(
                        checks,
                        f"{label}_planner_filter_finds_routine",
                        "Dashboard Dense Routine 00" in routine_filtered_body,
                        routine_filtered_body[:300],
                    )
                    planner_filter.fill("")
                    page.get_by_role("button", name="Tasks").click()
                    page.wait_for_timeout(200)
                    task_chip_body = page.locator("main").inner_text()
                    add_check(
                        checks,
                        f"{label}_planner_tasks_chip",
                        "Dashboard Dense Task 00" in task_chip_body
                        and "Dashboard Dense Idea 00" not in task_chip_body
                        and "Dashboard Dense Routine 00" not in task_chip_body,
                        task_chip_body[:400],
                    )
                    page.get_by_role("button", name="Ideas").click()
                    page.wait_for_timeout(200)
                    idea_chip_body = page.locator("main").inner_text()
                    add_check(
                        checks,
                        f"{label}_planner_ideas_chip",
                        "Dashboard Dense Idea 00" in idea_chip_body
                        and "Dashboard Dense Task 00" not in idea_chip_body,
                        idea_chip_body[:400],
                    )
                    page.get_by_role("button", name="Routines").click()
                    page.wait_for_timeout(200)
                    routine_chip_body = page.locator("main").inner_text()
                    add_check(
                        checks,
                        f"{label}_planner_routines_chip",
                        "Dashboard Dense Routine 00" in routine_chip_body
                        and "Dashboard Dense Task 00" not in routine_chip_body,
                        routine_chip_body[:400],
                    )
                    page.get_by_role("button", name="High priority").click()
                    page.wait_for_timeout(200)
                    high_priority_body = page.locator("main").inner_text()
                    add_check(
                        checks,
                        f"{label}_planner_high_priority_chip",
                        "Dashboard Browser Task" in high_priority_body
                        and "priority: high" in high_priority_body,
                        high_priority_body[:400],
                    )
                    page.get_by_role("button", name="Overdue").click()
                    page.wait_for_timeout(200)
                    overdue_body = page.locator("main").inner_text()
                    add_check(
                        checks,
                        f"{label}_planner_overdue_chip",
                        "Dashboard Browser Task" in overdue_body
                        and "state: overdue" in overdue_body,
                        overdue_body[:400],
                    )
                if route == "/knowledge":
                    visual_summaries.append(
                        visual_summary(page, viewport=label, route=route)
                    )
                    add_check(
                        checks,
                        f"{label}_knowledge_module_filter",
                        page.locator("[data-filter-input]").count() == 1,
                        body[:300],
                    )
                    add_check(
                        checks,
                        f"{label}_knowledge_semantic_items",
                        "Managed KBs" in body
                        and "Connectors" in body
                        and "Mounts" in body
                        and "dashboard_kb" in body
                        and "161 notes" in body,
                        body[:500],
                    )
                if route == "/library":
                    add_check(
                        checks,
                        f"{label}_library_semantic_items",
                        "Dashboard Browser Prompt" in body
                        and "Dashboard Dense Prompt 00" in body
                        and "dense-project-00" in body,
                        body[:500],
                    )
            page.goto(base_url, wait_until="networkidle")
            visual_summaries.append(visual_summary(page, viewport=label, route="/"))
            home_body = page.locator("body").inner_text()
            home_body_lower = home_body.lower()
            add_check(
                checks,
                f"{label}_home_clear_planner_label",
                "Themes to Practice" not in home_body
                and ("TODO Pins" in home_body or "Planner Queue" in home_body),
                home_body[:400],
            )
            add_check(
                checks,
                f"{label}_home_precise_index_labels",
                "searchable" in home_body_lower
                and "indexed records" in home_body_lower
                and "source families" in home_body_lower
                and "managed kb" in home_body_lower
                and "mount" in home_body_lower
                and "connector" in home_body_lower
                and "Indexed" not in home_body,
                home_body[:400],
            )
            search = page.locator("#global-search")
            add_check(checks, f"{label}_search_input", search.count() == 1)
            search.fill("Dashboard Browser")
            page.wait_for_timeout(400)
            result_text = page.locator("#search-results").inner_text()
            add_check(
                checks,
                f"{label}_search_results",
                "Dashboard Browser" in result_text,
                result_text[:200],
            )
            search.fill("Dashboard Dense Knowledge 41")
            page.wait_for_timeout(400)
            dense_result_text = page.locator("#search-results").inner_text()
            add_check(
                checks,
                f"{label}_dense_search_results",
                "Dashboard Dense Knowledge 41" in dense_result_text,
                dense_result_text[:240],
            )
            page.close()
        browser.close()

add_check(checks, "console_errors", not console_errors, "\n".join(console_errors[-5:]))
add_check(
    checks,
    "large_dataset_counts",
    large_dataset["pins"] >= 19
    and large_dataset["tasks_total"] >= 51
    and large_dataset["knowledge_items"] >= 161
    and large_dataset["search_index_items"] >= 250,
    json.dumps(large_dataset, ensure_ascii=False),
)
failed = [check for check in checks if check["status"] == "failed"]
payload = {
    "status": "failed" if failed else "passed",
    "routes_checked": len(routes) * len(viewports),
    "viewports": [{"name": name, "width": width, "height": height} for name, width, height in viewports],
    "large_dataset": large_dataset,
    "checks": checks,
    "visual_summaries": visual_summaries,
    "screenshots": str(screenshots),
    "console_errors": console_errors[-10:],
}
report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False, indent=2))
if failed:
    raise SystemExit("dashboard browser smoke failed")
PY
