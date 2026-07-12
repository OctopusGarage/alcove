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
            prompt = await client.get_prompt("todo_review")
            return resources, prompts, tasks, latest, prompt

    resources, prompts, tasks, latest, prompt = asyncio.run(run())

    assert "alcove://planner/tasks" in {str(resource.uri) for resource in resources}
    assert "todo_review" in {prompt.name for prompt in prompts}
    assert "Review Alcove" in tasks[0].text
    latest_payload = json.loads(latest[0].text)
    assert latest_payload["reports"]["tech-news"]["date"] == "2026-07-12"
    assert "Preserve task ids" in prompt.messages[0].content.text
