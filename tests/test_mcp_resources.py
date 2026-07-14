import asyncio
import json

from fastmcp import Client

from alcove.home import AlcoveHome
from alcove.mcp_server import create_mcp_server
from alcove.tasks import AddTaskRequest, TasksModule


def test_mcp_resources_and_prompts_are_available(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    TasksModule(home=home).task_add(AddTaskRequest(title="Review Alcove"))
    report_root = home.root / "radars/reports/tech-news"
    report_root.mkdir(parents=True)
    (report_root / "2026-07-12.md").write_text("# Tech\n", encoding="utf-8")
    (report_root / "2026-07-12.html").write_text("<h1>Tech</h1>", encoding="utf-8")
    mcp = create_mcp_server(default_home=str(home.root), toolset="lite")

    async def run():
        async with Client(mcp) as client:
            resources = await client.list_resources()
            prompts = await client.list_prompts()
            tasks = await client.read_resource("alcove://planner/tasks")
            latest = await client.read_resource("alcove://radars/latest")
            dated = await client.read_resource("alcove://radars/2026-07-12")
            prompt = await client.get_prompt("todo_review")
            return resources, prompts, tasks, latest, dated, prompt

    resources, prompts, tasks, latest, dated, prompt = asyncio.run(run())

    assert "alcove://planner/tasks" in {str(resource.uri) for resource in resources}
    assert "todo_review" in {prompt.name for prompt in prompts}
    assert "Review Alcove" in tasks[0].text
    latest_payload = json.loads(latest[0].text)
    dated_payload = json.loads(dated[0].text)
    assert latest_payload["reports"]["tech-news"]["date"] == "2026-07-12"
    assert dated_payload["date"] == "2026-07-12"
    assert dated_payload["reports"]["tech-news"]["md"].endswith("2026-07-12.md")
    assert dated_payload["reports"]["tech-news"]["html"].endswith("2026-07-12.html")
    assert "Preserve task ids" in prompt.messages[0].content.text


def test_mcp_radar_resources_include_ai_summary_attachment(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    report_root = home.root / "radars/reports/world-news"
    report_root.mkdir(parents=True)
    (report_root / "2026-07-13.md").write_text("# News\n", encoding="utf-8")
    (report_root / "2026-07-13.html").write_text("<h1>News</h1>", encoding="utf-8")
    (report_root / "2026-07-13.ai.md").write_text("# AI Summary\n", encoding="utf-8")
    mcp = create_mcp_server(default_home=str(home.root), toolset="lite")

    async def run():
        async with Client(mcp) as client:
            latest = await client.read_resource("alcove://radars/latest")
            dated = await client.read_resource("alcove://radars/2026-07-13")
            return json.loads(latest[0].text), json.loads(dated[0].text)

    latest_payload, dated_payload = asyncio.run(run())

    assert latest_payload["reports"]["world-news"]["ai.md"].endswith("2026-07-13.ai.md")
    assert dated_payload["reports"]["world-news"]["ai.md"].endswith("2026-07-13.ai.md")
