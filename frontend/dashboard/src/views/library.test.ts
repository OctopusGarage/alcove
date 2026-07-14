import { describe, expect, it } from "vitest";
import type { DashboardSnapshot } from "../snapshot";
import { renderLibrary } from "./library";

describe("dashboard library view", () => {
  it("renders prompts as structured reusable assets instead of a flat history blob", () => {
    const html = renderLibrary({
      prompts: [
        {
          id: "history-to-prompt",
          title: "历史输入到可复用 Prompt 萃取",
          description: "从历史 AI 对话、零散输入和项目讨论中提炼可复用 prompt，同时过滤一次性噪声和隐私信息。",
          content:
            "把历史 AI 对话、零散用户输入或项目讨论整理成可复用 Prompt 时，按这个流程执行：\n\n1. 先分层清洗\n- 保留目标、约束、验收标准。",
          kind: "playbook",
          domain: "prompt-engineering",
          intent: "prompt-curation",
          status: "active",
          tags: ["prompt", "curation"],
          use_cases: ["清洗 PromptPocket 或历史输入里的可复用资产"],
          triggers: ["提示词整理"],
          outputs: ["规范 prompt 记录"],
          surfaces: ["codex"],
        },
      ],
      projects: [{ alias: "alcove", note: "Local project", path_label: "alcove", exists: true }],
    } as unknown as DashboardSnapshot);

    expect(html).toContain("Prompt Library");
    expect(html).toContain("active prompts");
    expect(html).toContain("Search prompts");
    expect(html).toContain('data-filter-kind="playbook"');
    expect(html).toContain("Use when");
    expect(html).toContain("Expected output");
    expect(html).toContain("Prompt");
    expect(html).toContain("Copy prompt");
    expect(html).toContain('data-copy-target="prompt-body-0-history-to-prompt"');
    expect(html).toContain("把历史 AI 对话、零散用户输入或项目讨论整理成可复用 Prompt");
    expect(html).toContain("清洗 PromptPocket 或历史输入里的可复用资产");
    expect(html).not.toContain("preview truncated");
    expect(html).not.toContain("<p>从历史 AI 对话");
    expect(html).toContain("Project Shortcuts");
  });

  it("renders the full prompt body instead of truncating long prompts", () => {
    const longPrompt = `${"Review the current change.\n".repeat(60)}Final required line.`;
    const html = renderLibrary({
      prompts: [
        {
          id: "long-review-prompt",
          title: "Long Review Prompt",
          description: "Review thoroughly.",
          content: longPrompt,
          kind: "eval_prompt",
          domain: "testing",
          intent: "audit",
          status: "active",
          tags: ["audit"],
          use_cases: ["Regression review"],
          triggers: ["review"],
          outputs: ["findings"],
          surfaces: ["codex"],
        },
      ],
      projects: [],
    } as unknown as DashboardSnapshot);

    expect(html).toContain("Final required line.");
    expect(html).toContain('data-copy-target="prompt-body-0-long-review-prompt"');
    expect(html).not.toContain("[preview truncated");
    expect(html).not.toContain("use prompt get for full text");
  });

  it("keeps behavior notes out of the active prompt library", () => {
    const html = renderLibrary({
      prompts: [
        {
          id: "real-prompt",
          title: "实现完整性检查",
          description: "审查功能是否完整落地。",
          content: "请检查入口、数据、测试和文档是否完整。",
          kind: "eval_prompt",
          domain: "ai-coding",
          intent: "audit",
          status: "active",
          tags: ["audit"],
          use_cases: ["新功能收尾"],
          triggers: ["全面检查"],
          outputs: ["遗漏清单"],
          surfaces: ["codex"],
        },
        {
          id: "short-command-style",
          title: "短指令续跑与执行确认",
          description: "用户短指令行为规则。",
          content: "继续表示接着做。",
          kind: "style_profile",
          domain: "ai-coding",
          intent: "short-command-continuation",
          status: "active",
          tags: ["interaction"],
          use_cases: ["用户短句推进"],
          triggers: ["继续"],
          outputs: ["行为规则"],
          surfaces: ["codex"],
        },
        {
          id: "archived-source",
          title: "历史来源",
          description: "来源参考。",
          content: "source only",
          kind: "source_note",
          domain: "ai-coding",
          intent: "source",
          status: "active",
          tags: ["source"],
          use_cases: ["source"],
          triggers: [],
          outputs: ["source reference"],
          surfaces: ["codex"],
        },
      ],
      projects: [],
    } as unknown as DashboardSnapshot);

    expect(html).toContain("1</b><span>active prompts");
    expect(html).toContain("实现完整性检查");
    expect(html).not.toContain("短指令续跑与执行确认");
    expect(html).not.toContain("历史来源");
  });
});
