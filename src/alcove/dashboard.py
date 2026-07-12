from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

from alcove.blog_monitor import BlogMonitorModule
from alcove.connector_display import connector_display_name
from alcove.connector_sources import ConnectorSourceRegistry
from alcove.dashboard_search_index import build_dashboard_search_index
from alcove.external_index import ExternalIndexStore
from alcove.external_presentation import ExternalIndexedItemPresenter
from alcove.home import AlcoveHome
from alcove.markdown import MarkdownRepository, normalize_slug
from alcove.mounts import MountsModule
from alcove.paths import compact_user_path
from alcove.pins_import import PinsMarkdownImportModule
from alcove.pins import Pin, PinsModule
from alcove.projects import ProjectsModule
from alcove.prompts import PromptsModule
from alcove.radars import RadarModule
from alcove.tasks import TasksModule
from alcove.usage import UsageRecorder


DASHBOARD_SNAPSHOT_VERSION = 1
DASHBOARD_TIMEZONE = timezone(timedelta(hours=8))


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def dashboard_time_iso(value: str) -> str:
    if not value:
        return ""
    try:
        normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(DASHBOARD_TIMEZONE).isoformat(timespec="seconds")


@dataclass(frozen=True)
class ThemeDefinition:
    id: str
    title: str
    kind: str
    summary: str
    tags: list[str]
    keywords: list[str]


REGULAR_THEMES = [
    ThemeDefinition(
        id="agent-cli-workbench",
        title="AI Agent CLI 操作台",
        kind="regular",
        summary="Claude Code、Codex、tmux、上下文、模型和快捷键的日常操作参考。",
        tags=["agent-workflow", "claude-code", "codex", "developer-tools"],
        keywords=[
            "claude",
            "codex",
            "/plan",
            "/compact",
            "/context",
            "/effort",
            "/fork",
            "tmux",
            "快捷键",
            "statusline",
        ],
    ),
    ThemeDefinition(
        id="agent-engineering-system",
        title="Agent 工程化与工作流",
        kind="regular",
        summary="Skills、subagents、hooks、MCP、OpenSpec、Superpowers、Goal/Loop/Workflow 等工程化方法。",
        tags=["agent-engineering", "workflow", "skills", "mcp"],
        keywords=[
            "skill",
            "subagent",
            "hook",
            "mcp",
            "workflow",
            "openspec",
            "superpowers",
            "goal",
            "loop",
            "harness",
            "tdd",
            "adr",
            "prd",
        ],
    ),
    ThemeDefinition(
        id="knowledge-management-reference",
        title="个人知识库与资料源",
        kind="regular",
        summary="OKF、Apple Notes、GitHub Stars、个人知识库、文章下载与资料索引相关参考。",
        tags=["knowledge", "okf", "apple-notes", "github-stars"],
        keywords=[
            "知识库",
            "okf",
            "apple",
            "github star",
            "star",
            "笔记",
            "appnotes",
            "下载文章",
            "chrome收藏",
        ],
    ),
    ThemeDefinition(
        id="frontend-verification",
        title="前端、可视化与端到端验证",
        kind="regular",
        summary="Playground、frontend-design、Playwright、网页验证、PPT/图形输出等视觉和验证参考。",
        tags=["frontend", "playwright", "visual-design", "verification"],
        keywords=[
            "frontend",
            "playground",
            "playwright",
            "webapp",
            "视觉",
            "前端",
            "ppt",
            "libreoffice",
            "画图",
        ],
    ),
    ThemeDefinition(
        id="developer-command-snippets",
        title="开发命令与本机工具",
        kind="regular",
        summary="Git、curl、uv、brew、抓包、端口转发、签名、清理等高频命令片段。",
        tags=["commands", "git", "macos", "developer-tools"],
        keywords=[
            "git",
            "curl",
            "uv ",
            "brew",
            "抓包",
            "ssh",
            "端口",
            "ifconfig",
            "cleanup",
            "gpg",
        ],
    ),
    ThemeDefinition(
        id="writing-and-publishing",
        title="写作、README 与表达规范",
        kind="regular",
        summary="文章写作、GitHub Markdown、README 优化、英文表达和内容发布相关参考。",
        tags=["writing", "readme", "markdown", "english"],
        keywords=[
            "写文章",
            "markdown",
            "readme",
            "英文",
            "音标",
            "发布",
            "blog",
            "github markdown",
        ],
    ),
    ThemeDefinition(
        id="mac-automation-and-launchers",
        title="macOS 自动化与启动器",
        kind="regular",
        summary="AppleScript、osacompile、Edge 时区启动器、iPad 和本机清理等 macOS 使用经验。",
        tags=["macos", "automation", "launcher"],
        keywords=[
            "osacompile",
            "applescript",
            "edge",
            "时区",
            "启动器",
            "ipad",
            "macos",
            "清理电脑",
        ],
    ),
]

TODO_THEMES = [
    ThemeDefinition(
        id="knowledge-system-roadmap",
        title="知识库系统路线图",
        kind="todo",
        summary="数据看板、搜索记录、收藏夹、GitHub Stars、Chrome 收藏、Apple Notes 和私人 wiki 的后续建设。",
        tags=["knowledge", "dashboard", "roadmap"],
        keywords=[
            "数据看板",
            "搜索记录",
            "知识库",
            "github",
            "star",
            "chrome",
            "apple",
            "私人wiki",
            "mcp查询",
        ],
    ),
    ThemeDefinition(
        id="agent-evaluation-and-prompts",
        title="Agent Eval 与 Prompt 评估",
        kind="todo",
        summary="Prompt 打分、eval 数据集、grader、transcript、regression/capability eval 的实践任务。",
        tags=["eval", "prompt", "agent-engineering"],
        keywords=["eval", "grader", "transcript", "prompt", "评分", "regression", "capability"],
    ),
    ThemeDefinition(
        id="agent-governance-and-memory",
        title="Agent 规则、记忆与治理",
        kind="todo",
        summary="CLAUDE.md、Skills、Subagents、Hooks、MCP、ADR/PRD/BDD/Linter 闭环的落地任务。",
        tags=["agent-governance", "claude-code", "memory", "workflow"],
        keywords=[
            "claude.md",
            "subagent",
            "skills",
            "hooks",
            "mcp",
            "adr",
            "prd",
            "bdd",
            "linter",
            "记忆",
        ],
    ),
    ThemeDefinition(
        id="experiments-and-local-platform",
        title="实验项目与本地平台能力",
        kind="todo",
        summary="旧项目实验、PPT/网页验证、MySQL、Celery、异步任务和本地工具调用校验。",
        tags=["experiments", "platform", "webapp-testing"],
        keywords=[
            "过去的项目",
            "ppt",
            "webapp-testing",
            "playwright",
            "mysql",
            "celery",
            "异步任务",
            "tools调用",
        ],
    ),
    ThemeDefinition(
        id="model-and-language-learning",
        title="模型学习与语言训练",
        kind="todo",
        summary="模型蒸馏、自建模型、Anthropic 博文精读、英语输出比例和发音训练等学习任务。",
        tags=["model-learning", "english", "research"],
        keywords=["蒸馏", "模型", "anthropic", "30%", "英语", "音标", "博文"],
    ),
]


THEME_SECTION_RULES: dict[str, list[tuple[str, list[str]]]] = {
    "agent-cli-workbench": [
        ("CLI 会话与模型", ["claude", "codex", "model", "opus", "sonnet", "haiku"]),
        ("上下文与分支", ["/context", "/compact", "/export", "/branch", "/fork", "resume"]),
        ("快捷键与 TUI", ["ctrl", "cmd", "快捷键", "tui", "fullscreen", "statusline"]),
        ("插件与参考", ["plugin", "powerup", "playground", "awesome", "docs"]),
    ],
    "agent-engineering-system": [
        ("项目规则与记忆", ["claude.md", "rules", "memory", "adr", "prd", "bdd"]),
        ("Skills 与 Subagents", ["skill", "subagent", "agent", "reviewer"]),
        ("Workflow 与反馈循环", ["workflow", "loop", "eval", "grader", "tdd", "harness"]),
        ("外部工具与 MCP", ["mcp", "hook", "github", "slack", "playwright", "browser"]),
    ],
    "knowledge-management-reference": [
        ("知识入口", ["知识库", "笔记", "apple", "github star", "chrome", "收藏"]),
        ("索引与查询", ["okf", "index", "search", "mcp", "查询"]),
        ("采集与归档", ["下载", "文章", "归档", "inbox", "clipsmith"]),
    ],
    "frontend-verification": [
        ("设计参考", ["frontend", "design", "视觉", "ui", "taste", "impeccable"]),
        ("浏览器验证", ["playwright", "screenshot", "webapp", "chrome"]),
        ("文档与演示", ["ppt", "libreoffice", "html", "svg"]),
    ],
    "developer-command-snippets": [
        ("Git 与仓库", ["git", "commit", "branch", "remote", "gpg"]),
        ("Shell 与网络", ["curl", "ssh", "端口", "ifconfig", "抓包"]),
        ("本机工具", ["uv", "brew", "cleanup", "macos"]),
    ],
    "writing-and-publishing": [
        ("文章与 README", ["写文章", "readme", "markdown", "blog"]),
        ("语言表达", ["英文", "音标", "表达", "发布"]),
    ],
    "mac-automation-and-launchers": [
        ("启动器模式", ["osacompile", "applescript", "启动器", "edge", "时区"]),
        ("本机维护", ["ipad", "macos", "清理", "自动化"]),
    ],
    "knowledge-system-roadmap": [
        ("全局看板", ["数据看板", "搜索记录", "使用记录", "dashboard"]),
        ("置顶与个人资料", ["置顶", "收藏夹", "简单输入", "ai交流"]),
        ("多来源知识库", ["github", "star", "apple", "chrome", "私人wiki", "okf"]),
        ("采集与同步", ["下载文章", "git同步器", "mcp查询", "软链接"]),
    ],
    "agent-evaluation-and-prompts": [
        ("评估闭环", ["五步", "测试集", "批量", "评分器", "重跑"]),
        ("评分设计", ["grader", "平均分", "1-10", "transcript"]),
        ("上线策略", ["对比", "择优", "迭代", "regression", "capability"]),
    ],
    "agent-governance-and-memory": [
        ("上下文规则", ["claude.md", "memory", "项目宪法", "规则"]),
        ("Agent 分工", ["subagent", "skills", "reviewer", "frontmatter"]),
        ("工程闭环", ["hooks", "mcp", "adr", "prd", "bdd", "linter"]),
    ],
    "experiments-and-local-platform": [
        ("实验素材", ["过去的项目", "实验", "ppt", "webapp"]),
        ("本地服务", ["mysql", "celery", "异步任务", "进程"]),
        ("工具调用校验", ["tools调用", "用户校验", "规则编码"]),
    ],
    "model-and-language-learning": [
        ("模型实践", ["蒸馏", "模型", "做自己的模型"]),
        ("资料精读", ["anthropic", "博文", "研究"]),
        ("英语训练", ["英语", "音标", "中文", "30%"]),
    ],
}

CURATED_THEME_SECTIONS: dict[str, list[tuple[str, list[str]]]] = {
    "agent-cli-workbench": [
        (
            "会话控制",
            [
                "把 /plan、/compact、/context、/recap 当作长任务的节奏工具。",
                "跨天任务优先命名会话；需要保留主线时用 /branch 或 fork-session。",
                "复杂任务提高 effort；明确小任务降低 effort，避免无意义消耗。",
            ],
        ),
        (
            "日常快捷键",
            [
                "Ctrl+U 清空当前输入；Ctrl+R 搜索历史；Cmd+J 或 Option+Enter 换行。",
                "截图、长文本、临时问题要分流处理，避免污染主任务上下文。",
                "tmux 或 TUI 场景优先确认鼠标、滚动和输入历史模式是否冲突。",
            ],
        ),
        (
            "模型与插件",
            [
                "Sonnet 适合日常执行，Opus 适合复杂设计和审查，Haiku 适合快速问答。",
                "Powerup、Playground、automation recommender 更适合作为探索入口。",
                "外部 awesome 列表只作为候选池，真正复用前要先看安装方式和维护状态。",
            ],
        ),
    ],
    "agent-engineering-system": [
        (
            "项目规则层",
            [
                "CLAUDE.md、AGENTS.md、rules、ADR 和 PRD 承担长期记忆。",
                "规则要能被 hook、linter、CI 或 agent 审查引用，否则会变成没人执行的文档。",
                "本地个人覆盖文件和团队共享规则分开，避免把个人习惯写成项目事实。",
            ],
        ),
        (
            "执行编排层",
            [
                "小任务用单 agent 直接做；多文件中风险任务先规划；大批量独立任务再考虑 workflow。",
                "Subagent 适合隔离上下文和角色，不适合替代清晰的验收标准。",
                "Skills 要薄，脚本和命令沉到项目工具里，skill 只负责触发和路由。",
            ],
        ),
        (
            "反馈闭环",
            [
                "TDD、code review、Playwright 验证、gitleaks 和 CI 是 agent 长期可靠性的底座。",
                "Eval 和 transcript 阅读用于优化 prompt/workflow，不能只看最后一条回答。",
                "Goal 定义终点，Loop 负责评分，Workflow 沉淀复用步骤。",
            ],
        ),
    ],
    "knowledge-management-reference": [
        (
            "知识入口",
            [
                "托管知识库负责 inbox、OKF note 和归档；pins 负责高价值常看资料。",
                "Apple Notes、GitHub Stars、Chrome 收藏和网页采集都应该进入统一搜索。",
                "用户临时粘贴的笔记也应进入 inbox 或直接写成 OKF note。",
            ],
        ),
        (
            "索引策略",
            [
                "所有派生索引都要可重建，源文件仍是 Markdown、JSON export 或外部原始系统。",
                "Connector 和 mount 都应产生 OKF 风格索引，方便 agent 用普通文件搜索理解。",
                "命中外部索引后再 lazy fetch 原文，避免把所有外部系统复制进 Alcove。",
            ],
        ),
    ],
    "developer-command-snippets": [
        (
            "仓库操作",
            [
                "Git、commit、remote、签名和分支命令放在常规参考里，避免每次重新搜索。",
                "危险命令需要 hook 或 guardrail，不靠记忆提醒。",
                "一键脚本要输出做了什么、写到了哪里、如何回滚。",
            ],
        ),
        (
            "本机诊断",
            [
                "curl、ssh、端口、抓包、ifconfig 归为网络诊断工具组。",
                "uv、brew、cleanup 归为本机环境维护工具组。",
                "临时命令片段只保留可复用意图，不保存一次性输出噪音。",
            ],
        ),
    ],
    "mac-automation-and-launchers": [
        (
            "启动器模式",
            [
                "用 osacompile 把 AppleScript 包成 .app，适合固定环境变量、代理或时区启动。",
                "浏览器启动器优先复用原 profile，除非明确需要隔离会话。",
                "启动器说明要记录命令、环境变量、适用场景和回滚方式。",
            ],
        ),
        (
            "本机自动化",
            [
                "macOS 自动化适合做轻量入口，不适合承载复杂业务逻辑。",
                "涉及权限的脚本要记录系统授权位置和首次运行行为。",
            ],
        ),
    ],
    "knowledge-system-roadmap": [
        (
            "全局看板",
            [
                "记录搜索、使用、导入和整理行为，首页展示最近状态和关键入口。",
                "看板首版保持只读，写入继续通过 CLI、MCP 和 agent workflow 完成。",
                "后续可以按模块进入 pins、planner、knowledge、activity 等业务页面。",
            ],
        ),
        (
            "个人知识源",
            [
                "GitHub Stars、Apple Notes、Chrome 收藏、历史仓库和私人 wiki 都是可索引资料源。",
                "用户临时笔记、AI 对话整理和网页采集都应能进入托管知识库。",
                "外部资料源要支持增量刷新、删除同步和 OKF 派生索引。",
            ],
        ),
        (
            "分发与集成",
            [
                "Alcove 作为统一入口，采集工具和外部 connector 保持可替换。",
                "Hub 工作区、KB 工作区和全局 MCP 三种入口要各自保持轻重适中。",
            ],
        ),
    ],
    "agent-evaluation-and-prompts": [
        (
            "评估流程",
            [
                "先写 baseline prompt，再构建代表真实场景的数据集。",
                "批量运行样本并保留 transcript，评分器同时看输入、过程和输出。",
                "修改 prompt 后重跑同一数据集，用分数变化判断是否真的变好。",
            ],
        ),
        (
            "评分策略",
            [
                "Capability eval 看能力上限，regression eval 防止已有能力退化。",
                "Grader 不能只靠单一 LLM 判断，关键样本要人工抽查。",
                "平均分之外还要看失败分布，避免少数严重失败被均值掩盖。",
            ],
        ),
    ],
    "agent-governance-and-memory": [
        (
            "规则与记忆",
            [
                "CLAUDE.md 是项目宪法，Skills 是按需专家，Hooks 是事件守卫，MCP 是外部工具箱。",
                "Subagent 不会自动继承主会话 skills，必须在定义里显式声明。",
                "项目规则要和实际 hook、CI、linter 连接，形成可执行治理。",
            ],
        ),
        (
            "团队分工",
            [
                "不同 subagent 适合挂载不同 skills，例如前端审查、安全审查和 API 审查。",
                "共享规则适合进仓库，个人设置适合本地覆盖，分发能力再考虑 plugin。",
                "Agent 审查 agent 的价值在于独立上下文和明确职责。",
            ],
        ),
    ],
    "experiments-and-local-platform": [
        (
            "实验素材",
            [
                "旧项目可以作为 agent workflow、前端验证和工具调用的实验场。",
                "PPT、HTML、Playwright 和 LibreOffice 任务要保留可复查输出。",
                "实验项目要明确验收标准，否则容易变成工具堆砌。",
            ],
        ),
        (
            "平台能力",
            [
                "MySQL、Celery、异步任务和多进程运行适合作为后续本地平台能力验证。",
                "涉及用户级工具调用时要有确认、权限和日志记录。",
                "先做小闭环，再决定是否沉淀为正式模块。",
            ],
        ),
    ],
    "model-and-language-learning": [
        (
            "模型学习",
            [
                "模型蒸馏和自建模型先作为研究主题，记录资料、成本和可运行实验。",
                "Anthropic 等长文适合批量抓取后做主题精读和方法论提炼。",
            ],
        ),
        (
            "语言训练",
            [
                "英语输出比例、表达方式和发音材料应拆到独立学习资料里维护。",
                "技术学习笔记可以同时记录中文理解和英文表达模板。",
            ],
        ),
    ],
}


PIN_LINE_NOISE = {
    "",
    "===",
    "==",
    "---",
    "maybe use",
    "todo",
    "regular",
    "imported source",
    "一句话总结",
    "核心要点",
}


class DashboardModule:
    def __init__(self, home: AlcoveHome | None = None) -> None:
        self.home = home or AlcoveHome.init()
        self.root = self.home.root / "dashboard"

    def snapshot(self) -> dict[str, Any]:
        pins = PinsModule(home=self.home).list(status="")
        tasks = TasksModule(home=self.home)
        mounts = MountsModule(home=self.home)
        prompts = PromptsModule(home=self.home)
        projects = ProjectsModule(home=self.home)
        pending_tasks = tasks.task_list(status="pending")
        active_ideas = tasks.idea_list(status="active")
        active_routines = tasks.routine_list(status="active")
        all_tasks = tasks.task_list(status="")
        all_ideas = tasks.idea_list(status="")
        all_routines = tasks.routine_list(status="")
        prompt_rows = prompts.list(status="")
        project_rows = projects.list()
        mount_rows = mounts.list(status="")
        mount_items = mounts.index_items()
        connector_rows = self._connector_rows()
        radar_rows = RadarModule(self.home).dashboard_rows()
        blog_rows = self._blog_rows()
        kb_rows = self.home.list_knowledge_bases()
        knowledge_rows = self._knowledge_base_rows(kb_rows)
        usage_summary = UsageRecorder(self.home).summary()
        active_pins = [pin for pin in pins if pin.status == "active"]
        direct_pending_tasks = [
            task for task in pending_tasks if not str(task.source_routine_id or "")
        ]
        routine_due_tasks = [task for task in pending_tasks if str(task.source_routine_id or "")]
        theme_pins = [
            pin
            for pin in active_pins
            if "theme-pin" in pin.tags or "source-markdown-pin" in pin.tags
        ]
        activity = self._activity_rows()
        counts = {
            "pins": len(active_pins),
            "theme_pins": len(theme_pins),
            "regular_theme_pins": len([pin for pin in theme_pins if pin.kind == "regular"]),
            "todo_theme_pins": len([pin for pin in theme_pins if pin.kind == "todo"]),
            "pending_tasks": len(pending_tasks),
            "direct_pending_tasks": len(direct_pending_tasks),
            "routine_due_tasks": len(routine_due_tasks),
            "active_ideas": len(active_ideas),
            "active_routines": len(active_routines),
            "tasks_total": len(all_tasks),
            "ideas_total": len(all_ideas),
            "routines_total": len(all_routines),
            "prompts": len([prompt for prompt in prompt_rows if prompt.status == "active"]),
            "projects": len(project_rows),
            "mounts": len([mount for mount in mount_rows if mount.status == "active"]),
            "mount_items": len(mount_items),
            "connectors": len(connector_rows),
            "connector_items": sum(row["count"] for row in connector_rows),
            "radars": len(radar_rows),
            "radars_current": len([row for row in radar_rows if row["status"] == "current"]),
            "radars_configured": len([row for row in radar_rows if row["status"] == "configured"]),
            "radars_stale": len([row for row in radar_rows if row["status"] == "stale"]),
            "blog_sources": len(blog_rows),
            "blog_sources_active": len([row for row in blog_rows if row["status"] == "active"]),
            "knowledge_bases": len(kb_rows),
            "knowledge_items": sum(row["item_count"] for row in knowledge_rows),
            "activity_events": len(activity),
            "usage_events": usage_summary["total_events"],
        }
        mount_snapshot_rows = [self._mount_row(mount, mount_items) for mount in mount_rows]
        health = self._health_summary(
            knowledge_rows=knowledge_rows,
            connector_rows=connector_rows,
            mount_rows=mount_snapshot_rows,
            usage_summary=usage_summary,
        )
        snapshot = {
            "snapshot_version": DASHBOARD_SNAPSHOT_VERSION,
            "generated_at": now_iso(),
            "home": self._home_label(),
            "summary": {
                "title": "Alcove Dashboard",
                "subtitle": "Local-first personal knowledge workbench",
                "counts": counts,
            },
            "modules": self._modules(counts),
            "pins": {
                "themes": [self._theme_pin_dict(pin) for pin in theme_pins],
                "all": [self._pin_dict(pin) for pin in active_pins],
            },
            "tasks": {
                "pending": [self._task_dict(task) for task in pending_tasks],
                "ideas": [asdict(idea) for idea in active_ideas],
                "routines": [asdict(routine) for routine in active_routines],
                "all": [self._task_dict(task) for task in all_tasks],
                "ideas_all": [asdict(idea) for idea in all_ideas],
                "routines_all": [asdict(routine) for routine in all_routines],
            },
            "ideas": [asdict(idea) for idea in all_ideas],
            "routines": [asdict(routine) for routine in all_routines],
            "knowledge_bases": [
                {
                    "name": row["name"],
                    "item_count": row["item_count"],
                    "inbox_count": row["inbox_count"],
                    "archive_count": row["archive_count"],
                    "updated_at": row["updated_at"],
                }
                for row in knowledge_rows
            ],
            "knowledge": {"managed": knowledge_rows},
            "connectors": connector_rows,
            "mounts": mount_snapshot_rows,
            "radars": radar_rows,
            "blog_monitor": {"sources": blog_rows},
            "sources": {
                "connectors": connector_rows,
                "mounts": mount_snapshot_rows,
                "blogs": blog_rows,
            },
            "prompts": [
                {
                    "id": prompt.id,
                    "title": prompt.title,
                    "description": prompt.description,
                    "content": prompt.content,
                    "tags": prompt.tags,
                    "use_cases": prompt.use_cases,
                    "source_refs": prompt.source_refs,
                    "status": prompt.status,
                }
                for prompt in prompt_rows
            ],
            "projects": [
                {
                    "alias": project.alias,
                    "note": project.note,
                    "exists": project.exists,
                    "path_label": Path(project.path).expanduser().name
                    or compact_user_path(project.path),
                    "target_label": (
                        f"{project.alias} "
                        f"({Path(project.path).expanduser().name or compact_user_path(project.path)})"
                    ),
                    "command_hint": f"alcove project get {project.alias} --json",
                    "source": project.source,
                }
                for project in project_rows
            ],
            "activity": activity,
            "usage": usage_summary,
            "health": health,
        }
        snapshot["search_index"] = build_dashboard_search_index(snapshot)
        return snapshot

    def _home_label(self) -> str:
        return f"Alcove Home · {self.home.root.name or compact_user_path(self.home.root)}"

    def _task_dict(self, task: Any) -> dict[str, Any]:
        row = asdict(task)
        source_routine_id = str(row.get("source_routine_id") or "")
        row["generated_from_routine"] = bool(source_routine_id)
        row["instance_due"] = row.get("due") if source_routine_id else ""
        row["display_title"] = (
            f"{row.get('title', '')} (routine due)" if source_routine_id else row.get("title", "")
        )
        due = str(row.get("due") or "")
        status = str(row.get("status") or "")
        overdue_days = self._overdue_days(due) if status == "pending" else 0
        row["overdue"] = overdue_days > 0
        row["overdue_days"] = overdue_days
        row["due_state"] = "overdue" if overdue_days > 0 else ("due" if due else "")
        return row

    def _overdue_days(self, due: str) -> int:
        if not due:
            return 0
        try:
            due_date = datetime.fromisoformat(due).date()
        except ValueError:
            return 0
        today = datetime.now(DASHBOARD_TIMEZONE).date()
        return max((today - due_date).days, 0)

    def build(
        self,
        output_dir: str | Path | None = None,
        *,
        build_frontend: bool = True,
    ) -> dict[str, Any]:
        self._record_event("dashboard.build", "Built Alcove dashboard", visible=False)
        root = Path(output_dir).expanduser() if output_dir else self.root
        root.mkdir(parents=True, exist_ok=True)
        snapshot = self.snapshot()
        snapshot_path = root / "snapshot.json"
        snapshot_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        frontend = self._frontend_dir()
        frontend_built = False
        if build_frontend and frontend.is_dir():
            self._build_frontend(frontend, root)
            frontend_built = True
            snapshot_path.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        return {
            "status": "built",
            "root": str(root),
            "index": str(root / "index.html"),
            "snapshot": str(snapshot_path),
            "frontend_built": frontend_built,
            "frontend_mode": "compiled_frontend" if frontend_built else "static_snapshot",
            "frontend_note": (
                "Frontend build was skipped or unavailable; static index.html and snapshot.json "
                "were written for local dashboard use."
                if not frontend_built
                else ""
            ),
        }

    def import_pins(
        self,
        regular_file: str | Path | None = None,
        todo_file: str | Path | None = None,
    ) -> dict[str, Any]:
        result = PinsMarkdownImportModule(home=self.home).import_pins(
            regular_file=regular_file,
            todo_file=todo_file,
        )
        self._record_event(
            "dashboard.import_pins",
            "Imported regular/todo theme pin files",
            result,
        )
        return result

    def _theme_pin_dict(self, pin: Pin) -> dict[str, Any]:
        data = self._pin_dict(pin)
        data["sections"] = self._sections_from_content(pin.content)
        data["raw_excerpt"] = pin.content[:360].strip()
        return data

    def _sections_from_content(self, content: str) -> list[dict[str, str]]:
        sections: list[dict[str, str]] = []
        current_heading = ""
        current_body: list[str] = []
        for line in content.splitlines():
            if line.startswith("### "):
                if current_heading or current_body:
                    sections.append(
                        {
                            "heading": current_heading or "Notes",
                            "body": "\n".join(current_body).strip(),
                        }
                    )
                current_heading = line[4:].strip()
                current_body = []
            elif line.startswith("## "):
                continue
            elif current_heading:
                current_body.append(line)
        if current_heading or current_body:
            sections.append(
                {"heading": current_heading or "Notes", "body": "\n".join(current_body).strip()}
            )
        return [section for section in sections if section["body"]]

    def _pin_dict(self, pin: Pin) -> dict[str, Any]:
        return {
            "id": pin.id,
            "title": pin.title,
            "kind": pin.kind,
            "summary": pin.summary,
            "content": pin.content,
            "tags": pin.tags,
            "priority": pin.priority,
            "status": pin.status,
            "source_refs": pin.source_refs,
            "resources": pin.resources,
            "updated_at": pin.updated_at,
        }

    def _modules(self, counts: dict[str, int]) -> list[dict[str, Any]]:
        return [
            {
                "id": "pins",
                "title": "Pins",
                "subtitle": "Stable references and themes to revisit",
                "href": "/pins",
                "metric": counts["pins"],
                "detail": (
                    f"{counts['pins']} total pins / {counts['theme_pins']} theme pins "
                    f"({counts['regular_theme_pins']} regular themes / "
                    f"{counts['todo_theme_pins']} TODO themes)"
                ),
            },
            {
                "id": "knowledge",
                "title": "Knowledge",
                "subtitle": "Managed KBs, mounts, and connectors",
                "href": "/knowledge",
                "metric": (
                    counts["knowledge_items"] + counts["mount_items"] + counts["connector_items"]
                ),
                "detail": (
                    f"{self._count_phrase(counts['knowledge_items'], 'managed note')}, "
                    f"{self._count_phrase(counts['mount_items'], 'mounted file')}, "
                    f"{self._count_phrase(counts['connector_items'], 'connector item')}; "
                    f"{self._count_phrase(counts['knowledge_bases'], 'managed KB')}, "
                    f"{self._count_phrase(counts['mounts'], 'mount')}, "
                    f"{self._count_phrase(counts['connectors'], 'connector')}"
                ),
            },
            {
                "id": "planner",
                "title": "Planner",
                "subtitle": "Tasks, ideas, and routines",
                "href": "/planner",
                "metric": counts["tasks_total"] + counts["ideas_total"] + counts["routines_total"],
                "detail": (
                    f"{counts['direct_pending_tasks']} direct pending / "
                    f"{counts['routine_due_tasks']} routine due; "
                    f"{counts['tasks_total']} tasks / "
                    f"{counts['ideas_total']} ideas / {counts['routines_total']} routines"
                ),
            },
            {
                "id": "library",
                "title": "Library",
                "subtitle": "Prompts and project shortcuts",
                "href": "/library",
                "metric": counts["prompts"] + counts["projects"],
                "detail": f"{counts['prompts']} prompts / {counts['projects']} project shortcuts",
            },
            {
                "id": "activity",
                "title": "Activity",
                "subtitle": "Recent events and file changes",
                "href": "/activity",
                "metric": counts["activity_events"],
                "detail": (
                    f"Events and inferred changes; "
                    f"{counts['blog_sources_active']} active blog monitors"
                ),
            },
            {
                "id": "radars",
                "title": "Radars",
                "subtitle": "Scheduled information discovery",
                "href": "/radars",
                "metric": counts["radars"],
                "detail": (
                    f"{self._count_phrase(counts['radars'], 'radar')}; "
                    f"{counts['radars_current']} current / "
                    f"{counts['radars_configured']} configured / "
                    f"{counts['radars_stale']} stale"
                ),
            },
            {
                "id": "usage",
                "title": "Usage",
                "subtitle": "Search, actions, and data health",
                "href": "/usage",
                "metric": counts["usage_events"],
                "detail": f"{counts['usage_events']} local usage events",
            },
        ]

    def _count_phrase(self, count: int, singular: str, plural: str | None = None) -> str:
        label = singular if count == 1 else plural or f"{singular}s"
        return f"{count} {label}"

    def _blog_rows(self) -> list[dict[str, Any]]:
        sources = BlogMonitorModule(self.home).list_sources(status="").get("sources", [])
        rows = []
        for source in sources if isinstance(sources, list) else []:
            if not isinstance(source, dict):
                continue
            capture = source.get("capture") if isinstance(source.get("capture"), dict) else {}
            schedule = source.get("schedule") if isinstance(source.get("schedule"), dict) else {}
            rows.append(
                {
                    "id": str(source.get("id") or ""),
                    "name": str(source.get("name") or ""),
                    "url": str(source.get("url") or ""),
                    "status": str(source.get("status") or ""),
                    "checked_at": dashboard_time_iso(str(source.get("checked_at") or "")),
                    "changed_at": dashboard_time_iso(str(source.get("changed_at") or "")),
                    "capture_enabled": bool(capture.get("enabled")),
                    "kb": str(capture.get("kb") or ""),
                    "inbox_path": str(capture.get("inbox_path") or ""),
                    "ttl_hours": int(schedule.get("ttl_hours") or 0),
                }
            )
        return rows

    def _connector_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        registry = ConnectorSourceRegistry(home=self.home)
        status_by_key = {(row["connector"], row["id"]): row for row in registry.status()["sources"]}
        registered_connectors: set[str] = set()
        for source in registry.list():
            connector = str(source.get("connector") or "")
            source_id = str(source.get("id") or "")
            registered_connectors.add(connector)
            raw_refresh = source.get("refresh")
            refresh = raw_refresh if isinstance(raw_refresh, dict) else {}
            raw_status = status_by_key.get((connector, source_id), {})
            status = raw_status if isinstance(raw_status, dict) else {}
            rows.append(
                {
                    "connector": connector,
                    "id": source_id,
                    "source": self._connector_source_label(connector, source),
                    "status": str(status.get("status") or refresh.get("status") or ""),
                    "freshness_status": str(status.get("status") or refresh.get("status") or ""),
                    "count": int(status.get("item_count") or refresh.get("item_count") or 0),
                    "item_count": int(status.get("item_count") or refresh.get("item_count") or 0),
                    "checked_at": str(
                        status.get("checked_at")
                        or refresh.get("last_checked_at")
                        or refresh.get("last_changed_at")
                        or ""
                    ),
                    "ttl_hours": status.get("ttl_hours") or refresh.get("ttl_hours"),
                    "updated_at": str(
                        status.get("checked_at")
                        or refresh.get("last_checked_at")
                        or refresh.get("last_changed_at")
                        or ""
                    ),
                    "items": self._connector_items(connector, source_id),
                }
            )
        connectors_root = self.home.paths().connectors
        if not connectors_root.exists():
            return rows
        for index_path in sorted(connectors_root.glob("*/index.json")):
            if index_path.parent.name in registered_connectors:
                continue
            try:
                data = json.loads(index_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            items = data.get("items") if isinstance(data, dict) else None
            if not isinstance(items, list):
                items = []
            rows.append(
                self._fallback_connector_row(
                    connector=index_path.parent.name,
                    data=data,
                    item_count=len(items),
                    updated_at=datetime.fromtimestamp(index_path.stat().st_mtime, UTC).isoformat(
                        timespec="seconds"
                    ),
                )
            )
        return rows

    def _health_summary(
        self,
        *,
        knowledge_rows: list[dict[str, Any]],
        connector_rows: list[dict[str, Any]],
        mount_rows: list[dict[str, Any]],
        usage_summary: dict[str, Any],
    ) -> dict[str, Any]:
        data_sources: list[dict[str, Any]] = []
        for row in knowledge_rows:
            item_count = int(row.get("item_count") or 0)
            data_sources.append(
                {
                    "kind": "managed-kb",
                    "name": str(row.get("name") or ""),
                    "status": "ok" if item_count > 0 else "empty",
                    "item_count": item_count,
                    "inbox_count": int(row.get("inbox_count") or 0),
                    "updated_at": str(row.get("updated_at") or ""),
                    "command_hint": self._health_command_hint(
                        "managed-kb", str(row.get("name") or "")
                    ),
                }
            )
        for row in mount_rows:
            item_count = int(row.get("item_count") or 0)
            mount_id = str(row.get("id") or "")
            data_sources.append(
                {
                    "kind": "mount",
                    "name": str(row.get("name") or mount_id),
                    "status": "ok" if item_count > 0 else "empty",
                    "item_count": item_count,
                    "updated_at": str(row.get("updated_at") or ""),
                    "command_hint": self._health_command_hint("mount", mount_id),
                }
            )
        for row in connector_rows:
            raw_status = str(row.get("freshness_status") or row.get("status") or "")
            item_count = int(row.get("item_count") or row.get("count") or 0)
            connector = str(row.get("connector") or row.get("id") or "")
            data_sources.append(
                {
                    "kind": "connector",
                    "name": connector,
                    "status": raw_status or ("ok" if item_count > 0 else "empty"),
                    "item_count": item_count,
                    "updated_at": str(row.get("updated_at") or row.get("checked_at") or ""),
                    "command_hint": self._health_command_hint("connector", connector),
                }
            )
        totals = {
            "managed_kbs": len(knowledge_rows),
            "managed_items": sum(int(row.get("item_count") or 0) for row in knowledge_rows),
            "mounts": len(mount_rows),
            "mount_items": sum(int(row.get("item_count") or 0) for row in mount_rows),
            "connectors": len(connector_rows),
            "connector_items": sum(
                int(row.get("item_count") or row.get("count") or 0) for row in connector_rows
            ),
            "usage_events": int(usage_summary.get("total_events") or 0),
        }
        issue_count = len(
            [
                row
                for row in data_sources
                if str(row.get("status") or "") in {"empty", "stale", "error"}
            ]
        )
        stats_root = self.home.paths().stats
        daily_root = stats_root / "daily"
        return {
            "status": "needs-attention" if issue_count else "ok",
            "issue_count": issue_count,
            "totals": totals,
            "stats": {
                "summary_exists": (stats_root / "summary.json").is_file(),
                "daily_rollups": len(list(daily_root.glob("*.json"))) if daily_root.is_dir() else 0,
                "updated_at": self._latest_mtime(
                    [path for path in [stats_root / "summary.json"] if path.is_file()]
                ),
            },
            "data_sources": data_sources,
        }

    def _health_command_hint(self, kind: str, identifier: str) -> str:
        value = identifier.strip()
        if not value:
            return ""
        if kind == "managed-kb":
            return f"alcove validate --kb {value} --json"
        value = normalize_slug(value)
        if not value:
            return ""
        if kind == "mount":
            return f"alcove mount scan {value} --json"
        if kind == "connector":
            return f"alcove connector refresh --connector {value} --json"
        return ""

    def _fallback_connector_row(
        self,
        *,
        connector: str,
        data: dict[str, Any],
        item_count: int,
        updated_at: str,
    ) -> dict[str, Any]:
        ttl_hours = 24
        freshness_status = self._freshness_status(updated_at, ttl_hours)
        return {
            "id": connector,
            "connector": connector,
            "source": self._connector_source_label(connector, data),
            "status": freshness_status,
            "freshness_status": freshness_status,
            "count": item_count,
            "item_count": item_count,
            "checked_at": updated_at,
            "ttl_hours": ttl_hours,
            "updated_at": updated_at,
            "items": self._connector_items(connector, ""),
        }

    def _freshness_status(self, updated_at: str, ttl_hours: int) -> str:
        try:
            checked_at = datetime.fromisoformat(updated_at)
        except ValueError:
            return "indexed"
        age_seconds = (datetime.now(UTC) - checked_at).total_seconds()
        return "fresh" if age_seconds <= ttl_hours * 3600 else "stale"

    def _connector_source_label(self, connector: str, data: dict[str, Any]) -> str:
        public = self._public_resource(str(data.get("source") or ""))
        if public and public != connector:
            return public
        return connector_display_name(connector)

    def _knowledge_base_rows(self, kb_rows: list[Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for kb in kb_rows:
            all_knowledge_files = self._files_under(kb.path / "knowledge", "*.md")
            candidate_files = [
                path
                for path in all_knowledge_files
                if not self._is_structural_knowledge_path(path, kb.path)
            ]
            knowledge_files = [
                path for path in candidate_files if self._knowledge_file_status(path) != "deleted"
            ]
            deleted_item_count = len(candidate_files) - len(knowledge_files)
            inbox_files = self._files_under(kb.path / "inbox")
            archive_files = self._files_under(kb.path / "archive")
            omitted_items = [
                self._omitted_knowledge_item(path, kb.path) for path in knowledge_files[5:8]
            ]
            rows.append(
                {
                    "name": kb.name,
                    "item_count": len(knowledge_files),
                    "deleted_item_count": deleted_item_count,
                    "display_limit": 5,
                    "omitted_item_count": max(len(knowledge_files) - 5, 0),
                    "omitted_items": omitted_items,
                    "inbox_count": len(inbox_files),
                    "archive_count": len(archive_files),
                    "updated_at": self._latest_mtime(
                        [*all_knowledge_files, *inbox_files, *archive_files]
                    ),
                    "items": [
                        self._kb_item(file_path, kb.path) for file_path in knowledge_files[:5]
                    ],
                    "search_items": [
                        self._kb_search_item(file_path, kb.path) for file_path in knowledge_files
                    ],
                }
            )
        return rows

    def _knowledge_file_status(self, path: Path) -> str:
        try:
            doc = MarkdownRepository().read_doc(path)
        except OSError:
            return ""
        return str(doc.frontmatter.get("status") or "").casefold()

    def _files_under(self, root: Path, pattern: str = "*") -> list[Path]:
        if not root.is_dir():
            return []
        return [
            path
            for path in sorted(root.rglob(pattern), key=lambda item: item.as_posix())
            if path.is_file()
        ]

    def _latest_mtime(self, paths: list[Path]) -> str:
        if not paths:
            return ""
        return datetime.fromtimestamp(max(path.stat().st_mtime for path in paths), UTC).isoformat(
            timespec="seconds"
        )

    def _omitted_knowledge_item(self, path: Path, kb_root: Path) -> dict[str, str]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        doc = MarkdownRepository().read_doc(path)
        title = str(doc.frontmatter.get("title") or self._title_from_markdown(text) or path.stem)
        return {
            "title": title,
            "type": str(doc.frontmatter.get("type") or "Managed KB Item"),
            "relative_path": path.relative_to(kb_root).as_posix(),
            "search_hint": f'alcove search "{title}" --json',
        }

    def _kb_item(self, path: Path, kb_root: Path) -> dict[str, Any]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        doc = MarkdownRepository().read_doc(path)
        title = str(doc.frontmatter.get("title") or self._title_from_markdown(text) or path.stem)
        okf_type = str(doc.frontmatter.get("type") or "Managed KB Item")
        excerpt, truncated = self._clean_markdown_excerpt(text)
        return {
            "title": title,
            "type": okf_type,
            "okf_type": okf_type,
            "domain": str(doc.frontmatter.get("domain") or ""),
            "topic": str(doc.frontmatter.get("topic") or ""),
            "status": str(doc.frontmatter.get("status") or ""),
            "confidence": self._frontmatter_confidence(doc.frontmatter),
            "relative_path": path.relative_to(kb_root).as_posix(),
            "notes": excerpt,
            "truncated": truncated,
            "updated_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(
                timespec="seconds"
            ),
        }

    def _kb_search_item(self, path: Path, kb_root: Path) -> dict[str, str]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        doc = MarkdownRepository().read_doc(path)
        title = str(doc.frontmatter.get("title") or self._title_from_markdown(text) or path.stem)
        notes, _ = self._clean_markdown_excerpt(text, max_chars=320)
        return {
            "title": title,
            "type": str(doc.frontmatter.get("type") or "Managed KB Item"),
            "relative_path": path.relative_to(kb_root).as_posix(),
            "notes": notes,
        }

    def _frontmatter_confidence(self, frontmatter: dict[str, Any]) -> float:
        try:
            return round(float(frontmatter.get("confidence", 0.5) or 0.5), 2)
        except (TypeError, ValueError):
            return 0.5

    def _clean_markdown_excerpt(self, text: str, max_chars: int = 800) -> tuple[str, bool]:
        body = text
        if body.startswith("---\n"):
            _, separator, rest = body.partition("\n---\n")
            if separator:
                body = rest
        lines: list[str] = []
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped:
                if lines and lines[-1] != "":
                    lines.append("")
                continue
            if stripped.startswith(("[", "type:", "domain:", "topic:", "status:")):
                continue
            lines.append(line)
        excerpt = "\n".join(lines).strip()
        if len(excerpt) <= max_chars:
            return excerpt, False

        selected: list[str] = []
        current_len = 0
        for line in excerpt.splitlines():
            addition = len(line) + (1 if selected else 0)
            if selected and current_len + addition > max_chars:
                break
            if not selected and len(line) > max_chars:
                return self._truncate_line(line, max_chars), True
            selected.append(line)
            current_len += addition

        while selected and not selected[-1].strip():
            selected.pop()
        while selected and selected[-1].strip().startswith("#"):
            selected.pop()
            while selected and not selected[-1].strip():
                selected.pop()

        if not selected:
            return self._truncate_line(excerpt, max_chars), True
        return "\n".join(selected).strip(), True

    def _truncate_line(self, text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        cutoff = text.rfind(" ", 0, max_chars)
        if cutoff < max_chars // 2:
            cutoff = max_chars
        return text[:cutoff].rstrip()

    def _mount_row(self, mount: Any, mount_items: list[dict[str, Any]]) -> dict[str, Any]:
        all_items = [
            item for item in mount_items if str(item.get("mount_id") or "") == str(mount.id)
        ]
        items = [self._external_item(item) for item in all_items][:5]
        return {
            "id": mount.id,
            "name": mount.name,
            "type": mount.type,
            "tags": mount.tags,
            "status": mount.status,
            "created_at": mount.created_at,
            "updated_at": mount.updated_at,
            "items": items,
            "count": len(items),
            "item_count": len(all_items),
        }

    def _connector_items(
        self, connector: str, source_id: str, limit: int = 5
    ) -> list[dict[str, str]]:
        store = ExternalIndexStore(self.home.paths().connectors)
        items: list[dict[str, str]] = []
        for dataset in store.connector_datasets():
            if dataset.source_id != connector:
                continue
            for item in dataset.items:
                item_source_id = str(item.get("source_id") or "")
                if source_id and item_source_id and item_source_id.lower() != source_id.lower():
                    continue
                items.append(self._external_item(item))
                if len(items) >= limit:
                    return items
        return items

    def _external_item(self, item: dict[str, Any]) -> dict[str, Any]:
        presenter = ExternalIndexedItemPresenter.from_item(item)
        if presenter:
            return presenter.dashboard_item()
        text = str(item.get("text") or "")
        return {
            "title": str(item.get("title") or item.get("relative_path") or ""),
            "type": str(item.get("type") or item.get("source_kind") or "External Item"),
            "path": str(item.get("relative_path") or ""),
            "source": str(item.get("connector_name") or item.get("mount_name") or ""),
            "resource": self._public_resource(str(item.get("resource") or "")),
            "status": str(item.get("status") or "active"),
            "notes": text[:400],
            "updated_at": str(item.get("indexed_at") or item.get("updated_at") or ""),
        }

    def _title_from_markdown(self, text: str) -> str:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped.removeprefix("# ").strip()
            if stripped.startswith("title:"):
                return stripped.partition(":")[2].strip().strip("'\"")
        return ""

    def _activity_rows(self) -> list[dict[str, Any]]:
        paths: list[Path] = []
        for pattern in [
            "pins/*.md",
            "pins/imports/*.json",
            "prompts/*.md",
            "tasks/*.json",
            "projects/*.json",
            "mounts/**/*.json",
            "connectors/*/index.json",
            "knowledge-bases/*.yml",
        ]:
            paths.extend(self.home.root.glob(pattern))
        rows = self._event_rows()
        event_times_by_area = self._event_times_by_area(rows)
        for path in paths:
            if not path.is_file():
                continue
            area = path.relative_to(self.home.root).parts[0]
            if self._skip_activity_path(path):
                continue
            raw_updated_at = datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(
                timespec="seconds"
            )
            if self._is_derived_activity_update(area, raw_updated_at, event_times_by_area):
                continue
            rows.append(
                {
                    "type": "update",
                    "name": self._activity_name(path),
                    "area": area,
                    "detail": self._activity_detail(path),
                    "updated_at": dashboard_time_iso(raw_updated_at),
                    "raw_updated_at": raw_updated_at,
                }
            )
        return sorted(rows, key=lambda row: row["updated_at"], reverse=True)[:24]

    def _skip_activity_path(self, path: Path) -> bool:
        relative = path.relative_to(self.home.root)
        if relative.parts[0] == "pins" and len(relative.parts) == 2 and path.suffix == ".md":
            if path.stem == "index":
                return True
            try:
                pin = PinsModule(home=self.home).get(path.stem)
            except FileNotFoundError:
                return True
            if "source-markdown-pin" in pin.tags:
                return True
            return pin.status != "active"
        if (
            relative.parts[0] == "pins"
            and len(relative.parts) > 1
            and relative.parts[1] == "imports"
        ):
            return True
        if relative.parts[0] in {"connectors", "mounts"}:
            return True
        return False

    def _event_times_by_area(self, rows: list[dict[str, Any]]) -> dict[str, list[datetime]]:
        event_times: dict[str, list[datetime]] = {}
        for row in rows:
            if row.get("type") != "action":
                continue
            area = str(row.get("area") or "")
            raw_updated_at = str(row.get("raw_updated_at") or "")
            try:
                event_time = datetime.fromisoformat(raw_updated_at)
            except ValueError:
                continue
            event_times.setdefault(area, []).append(event_time)
        return event_times

    def _is_derived_activity_update(
        self,
        file_area: str,
        raw_updated_at: str,
        event_times_by_area: dict[str, list[datetime]],
    ) -> bool:
        event_area = {
            "pins": "pin",
            "prompts": "prompt",
            "projects": "project",
            "tasks": "task",
        }.get(file_area)
        if not event_area:
            return False
        try:
            file_time = datetime.fromisoformat(raw_updated_at)
        except ValueError:
            return False
        return any(
            abs((file_time - event_time).total_seconds()) <= 300
            for event_time in event_times_by_area.get(event_area, [])
        )

    def _activity_name(self, path: Path) -> str:
        relative = path.relative_to(self.home.root)
        area = relative.parts[0]
        if area == "pins":
            if len(relative.parts) > 1 and relative.parts[1] == "imports":
                return "Imported pin source saved"
            return "Pin updated"
        if area == "connectors":
            return (
                f"{relative.parts[1]} connector refreshed"
                if len(relative.parts) > 1
                else "Connector refreshed"
            )
        if area == "mounts":
            return "Mount refreshed"
        if area == "tasks":
            return "Planner updated"
        if area == "prompts":
            return "Prompt saved"
        if area == "projects":
            return "Project shortcut updated"
        if area == "knowledge-bases":
            return "Knowledge base changed"
        return f"{area} updated"

    def _activity_detail(self, path: Path) -> str:
        relative = path.relative_to(self.home.root)
        if relative.parts[0] == "pins" and path.suffix == ".md":
            try:
                pin = PinsModule(home=self.home).get(path.stem)
            except FileNotFoundError:
                return "Pin record changed"
            return pin.title
        if relative.parts[0] == "connectors" and len(relative.parts) > 1:
            return f"{relative.parts[1]} local search index"
        if relative.parts[0] == "mounts":
            return path.stem
        if relative.parts[0] == "tasks":
            return self._planner_activity_detail(path)
        if relative.parts[0] == "prompts" and path.suffix == ".md":
            try:
                prompt = PromptsModule(home=self.home).get(path.stem)
            except FileNotFoundError:
                return path.stem
            return prompt.title
        if relative.parts[0] == "projects":
            try:
                projects = ProjectsModule(home=self.home).list()
            except (FileNotFoundError, json.JSONDecodeError):
                return path.stem
            aliases = [project.alias for project in projects[:5]]
            return ", ".join(aliases) if aliases else path.stem
        return path.stem

    def _planner_activity_detail(self, path: Path) -> str:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return path.stem
        parts: list[str] = []
        for key, label in [("tasks", "tasks"), ("ideas", "ideas"), ("routines", "routines")]:
            values = data.get(key)
            if isinstance(values, dict):
                records = list(values.items())[:3]
            elif isinstance(values, list):
                records = [
                    (str(index), item)
                    for index, item in enumerate(values[:3])
                    if isinstance(item, dict)
                ]
            else:
                continue
            titles = [
                str(item.get("title") or item_id)
                for item_id, item in records
                if isinstance(item, dict)
            ]
            if titles:
                parts.append(f"{label}: {', '.join(titles)}")
        return "; ".join(parts) if parts else path.stem

    def _record_event(
        self,
        action: str,
        summary: str,
        metadata: dict[str, Any] | None = None,
        visible: bool = True,
    ) -> None:
        self._record_usage_event(action, summary, metadata or {})
        log_path = self.home.paths().logs / "activity.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "type": "event",
            "area": "dashboard",
            "action": action,
            "summary": summary,
            "metadata": metadata or {},
            "visible": visible,
            "updated_at": now_iso(),
        }
        with log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _record_usage_event(
        self,
        action: str,
        summary: str,
        metadata: dict[str, Any],
    ) -> None:
        recorder = UsageRecorder(self.home)
        if action == "dashboard.search":
            result_count = int(metadata.get("result_count") or 0)
            query_length = int(metadata.get("query_length") or 0)
            query_preview = str(metadata.get("query_preview") or "").strip()
            metrics: dict[str, Any] = {
                "query_length": max(query_length, 0),
                "result_count": max(result_count, 0),
            }
            if query_preview:
                metrics["query_preview"] = query_preview
            recorder.record_usage(
                surface="dashboard",
                area="search",
                action="search.run",
                summary=f"Search: {query_preview}" if query_preview else summary,
                outcome="empty" if result_count == 0 else "success",
                metrics=metrics,
                metadata={"filters": {}},
                privacy={
                    "query_stored": False,
                    "query_preview_stored": bool(query_preview),
                    "content_stored": False,
                },
            )
            return
        if action == "dashboard.route":
            recorder.record_usage(
                surface="dashboard",
                area="dashboard",
                action=action,
                summary=summary,
                metadata={"route": str(metadata.get("route") or "")},
                privacy={"query_stored": False, "content_stored": False},
            )
            return
        if action == "dashboard.result_open":
            recorder.record_usage(
                surface="dashboard",
                area="dashboard",
                action=action,
                summary=summary,
                metadata={
                    "type": str(metadata.get("type") or ""),
                    "href": str(metadata.get("href") or ""),
                    "title_length": int(metadata.get("title_length") or 0),
                },
                privacy={"query_stored": False, "content_stored": False},
            )

    def _event_rows(self) -> list[dict[str, Any]]:
        log_path = self.home.paths().logs / "activity.jsonl"
        if not log_path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line in log_path.read_text(encoding="utf-8").splitlines()[-100:]:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("action") in {
                "dashboard.build",
                "dashboard.route",
                "dashboard.search",
            }:
                continue
            if event.get("action") == "knowledge.delete":
                metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
                if str(metadata.get("confirmed") or "").casefold() != "true":
                    continue
            if not event.get("visible", True):
                continue
            raw_updated_at = str(event.get("updated_at") or "")
            rows.append(
                {
                    "type": "action",
                    "name": self._event_name(event),
                    "area": str(event.get("area") or "activity"),
                    "detail": self._event_detail(event),
                    "updated_at": dashboard_time_iso(raw_updated_at),
                    "raw_updated_at": raw_updated_at,
                }
            )
        return rows

    def _event_name(self, event: dict[str, Any]) -> str:
        action = str(event.get("action") or "")
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        title = str(metadata.get("title") or "").strip()
        if action == "knowledge.delete" and title:
            return f"Deleted knowledge: {title}"
        if action == "knowledge.revise" and title:
            return f"Revised knowledge: {title}"
        return str(event.get("summary") or action or "event")

    def _event_detail(self, event: dict[str, Any]) -> str:
        action = str(event.get("action") or "")
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        if action == "dashboard.import_pins":
            regular = metadata.get("regular") if isinstance(metadata, dict) else None
            todo = metadata.get("todo") if isinstance(metadata, dict) else None
            regular_count = regular.get("imported", 0) if isinstance(regular, dict) else 0
            todo_count = todo.get("imported", 0) if isinstance(todo, dict) else 0
            return f"{regular_count} regular themes, {todo_count} todo themes"
        if action in {"knowledge.delete", "knowledge.revise"}:
            path = str(metadata.get("path") or "").strip()
            return path or str(event.get("summary") or action or "event")
        return str(event.get("summary") or action or "event")

    def _is_structural_knowledge_path(self, path: Path, kb_root: Path) -> bool:
        try:
            relative_path = path.relative_to(kb_root).as_posix()
        except ValueError:
            return False
        return self._is_structural_knowledge_relative_path(relative_path)

    def _is_structural_knowledge_relative_path(self, relative_path: str) -> bool:
        return relative_path == "knowledge/index.md" or relative_path.startswith(
            (
                "knowledge/domains/",
                "knowledge/tags/",
                "knowledge/topics/",
            )
        )

    def _public_resource(self, value: str) -> str:
        if value.startswith(("~", "/", ".")):
            return ""
        return value

    def _frontend_dir(self) -> Path:
        return Path(__file__).resolve().parents[2] / "frontend" / "dashboard"

    def _build_frontend(self, frontend: Path, output_dir: Path) -> None:
        package_json = frontend / "package.json"
        if not package_json.is_file():
            return
        npm = shutil.which("npm")
        if npm is None:
            raise FileNotFoundError("npm is required to build the dashboard frontend")
        if not (frontend / "node_modules").is_dir():
            subprocess.run(  # noqa: S603
                [npm, "install"],
                cwd=frontend,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        subprocess.run(  # noqa: S603
            [npm, "run", "build"],
            cwd=frontend,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        dist = frontend / "dist"
        if not dist.is_dir():
            raise FileNotFoundError(f"Dashboard frontend build did not create {dist}")
        for path in dist.iterdir():
            target = output_dir / path.name
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            if path.is_dir():
                shutil.copytree(path, target)
            else:
                shutil.copy2(path, target)


def serve_dashboard(home: AlcoveHome, host: str = "127.0.0.1", port: int = 8765) -> None:
    result = DashboardModule(home=home).build()
    root = Path(result["root"])

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(root), **kwargs)

        def _apply_spa_fallback(self) -> None:
            requested = root / self.path.lstrip("/").split("?", 1)[0]
            if self.path not in {"/", ""} and not requested.exists():
                self.path = "/index.html"

        def do_GET(self) -> None:  # noqa: N802
            if self.path.split("?", 1)[0] == "/snapshot.json":
                self._send_dynamic_snapshot(include_body=True)
                return
            self._apply_spa_fallback()
            super().do_GET()

        def do_HEAD(self) -> None:  # noqa: N802
            if self.path.split("?", 1)[0] == "/snapshot.json":
                self._send_dynamic_snapshot(include_body=False)
                return
            self._apply_spa_fallback()
            super().do_HEAD()

        def do_POST(self) -> None:  # noqa: N802
            if self.path.split("?", 1)[0] != "/events":
                self.send_error(404)
                return
            self._record_client_event()

        def _send_dynamic_snapshot(self, *, include_body: bool) -> None:
            body = json.dumps(
                DashboardModule(home=home).snapshot(),
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if include_body:
                self.wfile.write(body)

        def _record_client_event(self) -> None:
            length = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(min(length, 16_384)) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self.send_error(400)
                return
            if not isinstance(payload, dict):
                self.send_error(400)
                return
            action = str(payload.get("action") or "dashboard.event")
            summary = str(payload.get("summary") or action)
            metadata = payload.get("metadata")
            DashboardModule(home=home)._record_event(
                action,
                summary,
                metadata if isinstance(metadata, dict) else {},
                visible=False,
            )
            self.send_response(204)
            self.end_headers()

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Alcove dashboard: http://{host}:{port}/")
    try:
        server.serve_forever()
    finally:
        server.server_close()
