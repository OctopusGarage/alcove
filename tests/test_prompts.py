from __future__ import annotations

import json
from pathlib import Path

from alcove.home import AlcoveHome
from alcove.markdown import MarkdownDoc, MarkdownRepository
from alcove.prompt_audit import PromptAuditModule
from alcove.prompt_ai_eval import evaluate_prompt_candidate
from alcove.prompt_composer import PromptComposerModule
from alcove.prompt_curation import PromptCurationModule
from alcove.prompt_proposals import PromptProposalModule
from alcove.prompt_quality import has_professional_contract, prompt_record_quality_score
from alcove.prompt_recommendation import PromptRecommendationModule
from alcove.prompts import AddPromptRequest, PromptsModule
from alcove.search import SearchModule, SearchRequest


def test_prompt_save_writes_okf_markdown_and_gets_full_content(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    module = PromptsModule(home=home)

    result = module.save(
        AddPromptRequest(
            title="Code Review Lens",
            content="Review for correctness, regressions, and missing tests.",
            description="Reusable code review prompt.",
            tags=["review", "quality"],
            use_cases=["PR review", "architecture review"],
            source_refs=["pins/review-principles.md"],
            kind="eval_prompt",
            domain="review",
            intent="review",
            surfaces=["codex", "claude-code"],
            triggers=["review this PR"],
            inputs=["diff", "requirements"],
            outputs=["findings"],
            quality={"status": "curated", "score": 0.92, "notes": "tested"},
        )
    )
    doc = MarkdownRepository().read_doc(result.path)
    prompt = module.get("code-review-lens")

    assert result.path == home.paths().prompts / "code-review-lens.md"
    assert doc.frontmatter["type"] == "Prompt"
    assert doc.frontmatter["schema"] == "okf/prompt/v1"
    assert doc.frontmatter["title"] == "Code Review Lens"
    assert doc.frontmatter["status"] == "active"
    assert doc.frontmatter["tags"] == ["quality", "review"]
    assert doc.frontmatter["source_refs"] == ["/pins/review-principles.md"]
    assert doc.frontmatter["use_cases"] == ["PR review", "architecture review"]
    assert doc.frontmatter["kind"] == "eval_prompt"
    assert doc.frontmatter["domain"] == "review"
    assert doc.frontmatter["surfaces"] == ["claude-code", "codex"]
    assert doc.frontmatter["quality"]["score"] == 0.92
    assert "## Prompt" in doc.body
    assert prompt.content == "Review for correctness, regressions, and missing tests."
    assert prompt.kind == "eval_prompt"
    assert prompt.triggers == ["review this PR"]
    assert result.index_path == home.paths().prompts / "index.json"
    index = json.loads(result.index_path.read_text(encoding="utf-8"))
    assert index["schema"] == "alcove/prompts-index/v1"
    assert index["count"] == 1
    assert index["prompts"][0]["schema"] == "okf/prompt/v1"
    assert index["prompts"][0]["path"] == "prompts/code-review-lens.md"
    assert index["prompts"][0]["kind"] == "eval_prompt"
    assert "missing tests" in index["prompts"][0]["search_text"]


def test_prompt_search_tags_and_archive(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    module = PromptsModule(home=home)
    module.save(
        AddPromptRequest(
            title="Bug Hunt",
            content="Find the root cause before patching.",
            tags=["debug"],
        )
    )
    module.save(
        AddPromptRequest(
            title="Writing Shape",
            content="Shape fragments into a clear article.",
            tags=["writing"],
        )
    )

    debug_prompts = module.search(query="root cause", tag="debug")
    tags = module.tags()
    archived = module.archive("bug-hunt", confirm=True)
    active_after_archive = module.search(query="")

    assert [prompt.title for prompt in debug_prompts] == ["Bug Hunt"]
    assert tags == [{"tag": "debug", "count": 1}, {"tag": "writing", "count": 1}]
    assert archived["status"] == "archived"
    assert [prompt.title for prompt in active_after_archive] == ["Writing Shape"]


def test_prompt_search_filters_kind_domain_and_surface(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    module = PromptsModule(home=home)
    module.save(
        AddPromptRequest(
            title="Agent Debug Playbook",
            content="Find root cause before patching.",
            tags=["debug"],
            kind="playbook",
            domain="debugging",
            surfaces=["codex"],
        )
    )
    module.save(
        AddPromptRequest(
            title="Article Prompt",
            content="Draft a concise article.",
            tags=["writing"],
            kind="full_prompt",
            domain="writing",
            surfaces=["generic-llm"],
        )
    )

    matches = module.search(kind="playbook", domain="debugging", surface="codex")

    assert [prompt.title for prompt in matches] == ["Agent Debug Playbook"]


def test_prompt_modifier_kind_is_preserved_and_recommendable(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    module = PromptsModule(home=home)
    result = module.save(
        AddPromptRequest(
            title="Autonomous Execution Suffix",
            content=(
                "Append this to implementation tasks when the goal is clear and "
                "the agent should proceed autonomously before reporting back."
            ),
            description="Composable suffix for autonomous agent execution.",
            tags=["agent-workflow"],
            use_cases=["Implementation tasks"],
            kind="modifier",
            domain="agent-automation",
            intent="execute",
            triggers=["autonomous execution"],
            outputs=["completion report"],
        )
    )

    prompt = module.get("autonomous-execution-suffix")
    recommendations = PromptRecommendationModule(home=home).recommend(
        "autonomous execution for a clear implementation task"
    )

    assert result.prompt.kind == "modifier"
    assert prompt.kind == "modifier"
    assert recommendations[0].prompt.title == "Autonomous Execution Suffix"


def test_prompt_recommend_matches_chinese_modifier_scenario(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    PromptsModule(home=home).save(
        AddPromptRequest(
            title="修饰语·并行subagent",
            content="用多个并行 subagent 按模块或风险维度同时检查，再汇总去重。",
            description="可附加到审查或调研任务末尾。",
            tags=["审查", "并行"],
            use_cases=["大型代码库审查"],
            kind="modifier",
            domain="agent-automation",
            intent="decompose",
            triggers=["需要多维度审查"],
            outputs=["去重后的汇总问题"],
        )
    )

    recommendations = PromptRecommendationModule(home=home).recommend(
        "这个任务范围很大，需要并行多维度审查并汇总去重"
    )

    assert recommendations[0].prompt.title == "修饰语·并行subagent"
    assert recommendations[0].score > 0


def test_prompt_recommend_scores_matching_scenario(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    module = PromptsModule(home=home)
    module.save(
        AddPromptRequest(
            title="Dashboard Regression Review",
            content="Review dashboard data consistency and missing tests.",
            description="Use before shipping dashboard changes.",
            tags=["review", "dashboard"],
            use_cases=["Dashboard review"],
            triggers=["dashboard bug"],
            kind="eval_prompt",
            domain="review",
            quality={"score": 0.9},
        )
    )
    module.save(
        AddPromptRequest(
            title="Image Prompt",
            content="Create image prompts.",
            tags=["image"],
            domain="creative-media",
        )
    )

    recommendations = PromptRecommendationModule(home=home).recommend(
        "dashboard bug needs review and regression tests"
    )

    assert recommendations[0].prompt.title == "Dashboard Regression Review"
    assert recommendations[0].score > 0.5
    assert recommendations[0].reasons


def test_prompt_recommend_defaults_to_five_candidates(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    module = PromptsModule(home=home)
    for index in range(7):
        module.save(
            AddPromptRequest(
                title=f"Regression Review {index}",
                content=f"Review regression risk, tests, and verification evidence {index}.",
                description="Regression review prompt.",
                tags=["review", "regression"],
                use_cases=["Regression review"],
                outputs=["findings"],
                kind="eval_prompt",
                domain="testing",
                quality={"score": 0.9},
            )
        )

    recommendations = PromptRecommendationModule(home=home).recommend("regression review")

    assert len(recommendations) == 5


def test_prompt_recommend_filters_weak_behavior_preference_matches(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    PromptsModule(home=home).save(
        AddPromptRequest(
            title="Context Handoff",
            content=(
                "Write a compact handoff summary and avoid repeating explanations "
                "when another agent resumes the same task."
            ),
            description="Use before context compression or agent handoff.",
            tags=["handoff", "context"],
            use_cases=["Context handoff"],
            outputs=["handoff summary"],
            kind="full_prompt",
            domain="prompt-engineering",
            quality={"score": 0.95},
        )
    )

    recommendations = PromptRecommendationModule(home=home).recommend(
        "我说继续或者推送吧时自动执行，不要重复解释"
    )

    assert recommendations == []


def test_prompt_recommend_filters_short_command_mapping_queries(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    PromptsModule(home=home).save(
        AddPromptRequest(
            title="实现完整性检查",
            content="检查入口、数据、索引、dashboard、文档和残留逻辑。",
            description="审查功能是否从入口、数据、测试、文档到回归都完整落地。",
            tags=["implementation", "audit"],
            use_cases=["新功能收尾", "重构后复核"],
            triggers=["做完了吗", "全面检查"],
            kind="eval_prompt",
            domain="ai-coding",
            intent="audit",
            quality={"score": 0.94},
        )
    )

    recommendations = PromptRecommendationModule(home=home).recommend(
        "我说继续、推送吧、做完了吗时你要自动理解"
    )

    assert recommendations == []


def test_prompt_quality_accepts_reusable_operational_contract(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    prompt = (
        PromptsModule(home=home)
        .save(
            AddPromptRequest(
                title="Evidence First Regression Review",
                content=(
                    "Review the current change for correctness, regression risk, and "
                    "missing verification evidence. Read the relevant files before "
                    "reporting. Output only findings with file references, impact, and "
                    "a concrete remediation. If there are no findings, report residual "
                    "test gaps and state what was verified."
                ),
                description="Reusable review prompt for implementation changes.",
                tags=["review", "regression"],
                use_cases=["Code review", "Release readiness check"],
                outputs=["Findings", "Residual risks"],
                kind="eval_prompt",
                domain="review",
                intent="quality-review",
                quality={"score": 0.92},
            )
        )
        .prompt
    )

    assert has_professional_contract(prompt) is True
    assert prompt_record_quality_score(prompt) >= 0.9


def test_prompt_quality_rejects_chat_artifacts_and_template_boilerplate(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    prompts = PromptsModule(home=home)
    chat_artifact = prompts.save(
        AddPromptRequest(
            title="短指令续跑与执行确认",
            content=(
                "我经常用一两个字推进任务。\n- 继续 = 接着上次工作。\n- 推送吧 = 直接提交推送。"
            ),
            description="场景交互规则。",
            tags=["interaction"],
            kind="style_profile",
            quality={"score": 0.95},
        )
    ).prompt
    boilerplate = prompts.save(
        AddPromptRequest(
            title="Generic Prompt Template",
            content=(
                "Role and purpose\n"
                "Required inputs\n"
                "Operating rules\n"
                "Output contract\n"
                "Guardrails and stop conditions"
            ),
            description="可粘贴 prompt 片段。",
            tags=["template"],
            quality={"score": 0.95},
        )
    ).prompt

    assert has_professional_contract(chat_artifact) is False
    assert prompt_record_quality_score(chat_artifact) < 0.75
    assert has_professional_contract(boilerplate) is False
    assert prompt_record_quality_score(boilerplate) < 0.75


def test_prompt_quality_rejects_missing_title_commitments(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    prompt = (
        PromptsModule(home=home)
        .save(
            AddPromptRequest(
                title="Delivery Verification Rerun Hardening",
                content=(
                    "Review the current change before delivery. Run relevant checks, report "
                    "evidence, and list residual risks."
                ),
                description="Verify delivery before reporting completion.",
                tags=["testing"],
                outputs=["evidence", "risks"],
                kind="eval_prompt",
                domain="testing",
                intent="audit",
                quality={"score": 0.95},
            )
        )
        .prompt
    )

    assert has_professional_contract(prompt) is False
    assert prompt_record_quality_score(prompt) < 0.75
    ai_eval = evaluate_prompt_candidate(prompt)
    assert ai_eval["verdict"] == "needs_revision"
    assert any("hardening" in item for item in ai_eval["must_fix"])
    assert "Prompt Library Quality Reviewer" in ai_eval["reviewer_prompt"]


def test_prompt_recommend_filters_generic_chinese_verb_matches(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    PromptsModule(home=home).save(
        AddPromptRequest(
            title="历史输入到可复用 Prompt 萃取",
            content="从历史材料里提取真正可复用的 prompt，并整理、去重、归档。",
            description="从历史材料里提取真正可复用的 prompt。",
            tags=["prompt-curation"],
            use_cases=["整理历史提示词归档", "清理历史材料"],
            outputs=["optimized prompts"],
            kind="playbook",
            domain="prompt-engineering",
            intent="prompt-curation",
            quality={"score": 0.94},
        )
    )

    recommendations = PromptRecommendationModule(home=home).recommend("整理 podcast 剧集元数据")

    assert recommendations == []


def test_prompt_recommend_downranks_generic_skill_matches(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    module = PromptsModule(home=home)
    module.save(
        AddPromptRequest(
            title="浏览器工作流 Skill Builder",
            content="把手动网页操作流程整理成可复用 Skill。",
            description="将一个手动网页操作流程沉淀为可复用 Skill。",
            tags=["agent-automation", "browser", "skill-design"],
            use_cases=["把网页操作沉淀成 Skill"],
            triggers=["做成 skill", "浏览器自动化"],
            kind="playbook",
            domain="agent-automation",
            intent="skill-design",
            quality={"score": 0.94},
        )
    )
    module.save(
        AddPromptRequest(
            title="重复工作流沉淀扫描",
            content="扫描近期工作记录，找出重复流程、脚本、检查清单或 Skill 机会。",
            description="从近期工作记录中找出值得沉淀的重复流程。",
            tags=["workflow-mining", "automation"],
            use_cases=["扫描近期工作流"],
            triggers=["重复流程", "沉淀工作流"],
            kind="eval_prompt",
            domain="prompt-engineering",
            intent="workflow-mining",
            quality={"score": 0.94},
        )
    )

    recommendations = PromptRecommendationModule(home=home).recommend(
        "扫描最近一个月工作记录，看看哪些重复流程值得做成 skill、脚本或检查清单"
    )

    assert recommendations[0].prompt.title == "重复工作流沉淀扫描"
    assert "浏览器工作流 Skill Builder" not in [item.prompt.title for item in recommendations]


def test_prompt_recommend_applies_relative_cutoff_for_single_intent(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    module = PromptsModule(home=home)
    module.save(
        AddPromptRequest(
            title="证据优先代码评审",
            content="Review current diff for correctness, regression risk, and data consistency.",
            description="独立阅读 diff 和相关代码，只报告有证据的实质问题。",
            tags=["code-review", "evidence"],
            use_cases=["本地 diff 审查"],
            triggers=["review diff"],
            kind="eval_prompt",
            domain="review",
            intent="code-review",
            quality={"score": 0.95},
        )
    )
    module.save(
        AddPromptRequest(
            title="业务与设计审查",
            content="审查功能是否满足业务目标。",
            description="审查功能是否满足业务目标、用户流程和设计约束。",
            tags=["product-review", "review"],
            kind="eval_prompt",
            domain="product-review",
            intent="audit",
            quality={"score": 0.94},
        )
    )
    module.save(
        AddPromptRequest(
            title="功能与布局体验审查",
            content="检查 dashboard 的数据一致性、移动端布局和按钮入口。",
            description="用真实页面和截图审查功能入口、布局、移动端和数据展示。",
            tags=["ux", "dashboard", "review"],
            use_cases=["Dashboard 复核", "移动端体验检查"],
            kind="eval_prompt",
            domain="ux-review",
            intent="audit",
            quality={"score": 0.94},
        )
    )

    recommendations = PromptRecommendationModule(home=home).recommend(
        "review 当前 diff，重点看有没有真实回归和数据一致性问题"
    )

    assert [item.prompt.title for item in recommendations] == ["证据优先代码评审"]


def test_prompt_recommend_keeps_multiple_clear_intents(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    module = PromptsModule(home=home)
    module.save(
        AddPromptRequest(
            title="内容视觉资产 Prompt 设计",
            content="为文章、产品说明或课程内容设计配图 prompt、插图和视觉资产。",
            description="为文章、产品说明或课程内容设计可生成的视觉资产 prompt。",
            tags=["visual-design", "image-prompt"],
            use_cases=["为文章或产品内容设计配图 prompt"],
            triggers=["配图", "配图 prompt", "发布素材"],
            kind="full_prompt",
            domain="creative-media",
            intent="visual-asset-prompt-design",
            quality={"score": 0.94},
        )
    )
    module.save(
        AddPromptRequest(
            title="项目文档体系规划与发布",
            content="整理 README、docs、文档入口和发布方式。",
            description="为一个项目梳理真实文档体系，并建立可维护、可发布的文档入口。",
            tags=["documentation", "project-docs"],
            use_cases=["整理项目文档体系"],
            triggers=["文档入口", "发布文档站"],
            kind="playbook",
            domain="documentation",
            intent="documentation-system-design",
            quality={"score": 0.94},
        )
    )

    recommendations = PromptRecommendationModule(home=home).recommend(
        "帮文章整理发布素材，包括配图 prompt 和文档入口"
    )

    assert [item.prompt.title for item in recommendations] == [
        "内容视觉资产 Prompt 设计",
        "项目文档体系规划与发布",
    ]


def test_prompt_proposal_curates_and_detects_similar_existing_prompt(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    PromptsModule(home=home).save(
        AddPromptRequest(
            title="Dashboard Regression Review",
            content="Review dashboard data consistency, regression risk, and missing tests.",
            description="Use before shipping dashboard changes.",
            tags=["dashboard", "review"],
            use_cases=["Dashboard review"],
            outputs=["findings"],
            kind="eval_prompt",
            domain="testing",
            intent="review",
            quality={"score": 0.9},
        )
    )

    proposal = PromptProposalModule(home=home).propose(
        AddPromptRequest(
            title="dashboard review",
            content="Review dashboard data consistency, regression risk, missing tests, and user-facing behavior before release.",
        )
    )

    assert proposal["status"] == "proposed"
    assert proposal["action"] in {"update_existing", "create_new_after_review"}
    assert proposal["request"]["kind"] == "eval_prompt"
    assert proposal["request"]["description"]
    assert proposal["request"]["outputs"]
    assert proposal["similar"][0]["prompt"]["title"] == "Dashboard Regression Review"
    assert proposal["evaluation"]["checks"]["dedupe_checked"] is True
    assert proposal["evaluation"]["verdict"] in {
        "update_existing",
        "ready",
        "needs_review",
    }
    assert proposal["next_steps"]


def test_prompt_save_from_update_proposal_targets_existing_prompt(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    prompts = PromptsModule(home=home)
    prompts.save(
        AddPromptRequest(
            title="Dashboard Regression Review",
            content="Review dashboard data consistency and missing tests.",
            description="Use before shipping dashboard changes.",
            tags=["dashboard", "review"],
            use_cases=["Dashboard review"],
            outputs=["findings"],
            kind="eval_prompt",
            domain="testing",
            intent="review",
            quality={"score": 0.9},
        )
    )
    proposal = PromptProposalModule(home=home).propose(
        AddPromptRequest(
            title="dashboard review",
            content="Review dashboard data consistency, regression risk, missing tests, and user-facing behavior before release.",
        )
    )

    request = PromptProposalModule(home=home).request_from_proposal(proposal["id"])
    saved = prompts.save(request)
    all_prompts = prompts.list(status="active")

    assert proposal["action"] == "update_existing"
    assert request.title == "Dashboard Regression Review"
    assert saved.prompt.id == "dashboard-regression-review"
    assert len(all_prompts) == 1
    assert "user-facing behavior" in prompts.get("dashboard-regression-review").content


def test_prompt_save_from_proposal_uses_curated_request(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    proposal = PromptProposalModule(home=home).propose(
        AddPromptRequest(
            title="Prompt Curation Review",
            content="Review raw prompt history, remove one-off material, merge duplicates, and return reusable prompt records with metadata.",
        )
    )

    request = PromptProposalModule(home=home).request_from_proposal(proposal["id"])
    saved = PromptsModule(home=home).save(request)
    prompt = PromptsModule(home=home).get(saved.prompt.id)

    assert prompt.title == "Prompt Curation Review"
    assert prompt.description
    assert prompt.use_cases
    assert prompt.outputs
    assert prompt.quality["status"] == "proposed"


def test_prompt_proposal_anonymizes_personal_source_refs(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")

    proposal = PromptProposalModule(home=home).propose(
        AddPromptRequest(
            title="Prompt Guidelines Review",
            content=(
                "Review prompt text for clear instructions, explicit output, "
                "privacy boundaries, and duplicate overlap before saving."
            ),
            source_refs=[
                "~/programming/user/prompt-archive/docs/prompt-guidelines/Claude_Code_Prompt.md",
                "~/programming/user/ai-input-archive/samples.txt",
            ],
        )
    )

    assert proposal["request"]["source_refs"] == [
        "source:prompt-guidelines",
        "source:historical-ai-input-archive",
    ]


def test_prompt_recommend_treats_empty_surfaces_as_generic(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    module = PromptsModule(home=home)
    module.save(
        AddPromptRequest(
            title="Generic Regression Review",
            content="Review regression risk and verification evidence.",
            tags=["review"],
            kind="eval_prompt",
            quality={"score": 0.9},
        )
    )
    module.save(
        AddPromptRequest(
            title="Claude Only Writing",
            content="Draft prose.",
            tags=["writing"],
            surfaces=["claude-code"],
        )
    )

    recommendations = PromptRecommendationModule(home=home).recommend(
        "regression review",
        surface="codex",
    )

    assert [item.prompt.title for item in recommendations] == ["Generic Regression Review"]


def test_prompt_compose_builds_ready_to_use_prompt_pack(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    PromptsModule(home=home).save(
        AddPromptRequest(
            title="Dashboard Regression Review",
            content="Review dashboard data consistency and missing tests.",
            description="Use before shipping dashboard changes.",
            tags=["review", "dashboard"],
            triggers=["dashboard bug"],
            kind="eval_prompt",
            domain="review",
            quality={"score": 0.9},
        )
    )

    composed = PromptComposerModule(home=home).compose(
        "dashboard bug needs regression review",
        limit=2,
    )

    assert composed.sources[0].prompt.title == "Dashboard Regression Review"
    assert "# Alcove Prompt Pack" in composed.prompt
    assert "dashboard bug needs regression review" in composed.prompt
    assert "Review dashboard data consistency" in composed.prompt
    assert "Final Task" in composed.prompt


def test_prompt_audit_flags_metadata_duplicates_and_unportable_refs(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    module = PromptsModule(home=home)
    duplicate = (
        "Review the implementation for regressions and missing verification evidence. "
        "Check the diff, tests, user-facing behavior, and residual risks before approval."
    )
    module.save(
        AddPromptRequest(
            title="Review One",
            content=duplicate,
            source_refs=[str(Path.home() / "source.md")],
        )
    )
    module.save(
        AddPromptRequest(
            title="Review Two",
            content=duplicate,
            description="Another review prompt.",
            tags=["review"],
            use_cases=["Code review"],
            source_refs=["~/programming/example/private-source.md"],
            outputs=["findings"],
        )
    )
    module.save(
        AddPromptRequest(
            title="Ready Prompt",
            content=(
                "Use this during code review.\n\n"
                "Check the diff, nearby code, tests, and user acceptance criteria. "
                "Report only evidence-backed findings. Each finding must explain the "
                "risk, consequence, and smallest fix.\n\n"
                "Output findings, residual risks, and verification result. Do not invent "
                "issues or report low-confidence style opinions as defects.\n\n"
                "Verify conclusions against the diff, tests, or observable command output."
            ),
            description="Complete review prompt.",
            tags=["review"],
            use_cases=["Code review"],
            kind="eval_prompt",
            domain="review",
            intent="review",
            surfaces=["codex"],
            triggers=["review"],
            outputs=["findings"],
            quality={"score": 0.9},
        )
    )

    report = PromptAuditModule(home=home).audit()

    assert report["status"] == "issues"
    assert report["counts"]["prompts"] == 3
    assert report["counts"]["ready_prompts"] == 1
    kinds = {issue["kind"] for issue in report["issues"]}
    assert "missing_description" in kinds
    assert "missing_domain" in kinds
    assert "duplicate_content" in kinds
    assert "unportable_source_ref" in kinds
    assert "personal_source_ref" in kinds
    assert "weak_prompt_contract" in kinds
    assert any("absolute source refs" in item for item in report["recommendations"])
    assert any("stable source labels" in item for item in report["recommendations"])
    assert any("concise, actionable prompts" in item for item in report["recommendations"])


def test_prompt_audit_rejects_historical_note_style_prompts(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    PromptsModule(home=home).save(
        AddPromptRequest(
            title="用户交互风格：push",
            content=(
                '我经常用一两个字推进任务。 "继续" = 接着上次工作做下去；'
                '"推送吧" = 直接 git commit + push。'
            ),
            description="从历史 AI 输入中提炼的 push 场景交互规则。",
            tags=["style-profile"],
            use_cases=["指导 AI agent 正确响应用户意图"],
            kind="style_profile",
            domain="ai-coding",
            intent="push",
            surfaces=["codex"],
            triggers=["继续"],
            outputs=["行为约束"],
            quality={"score": 0.95},
        )
    )

    report = PromptAuditModule(home=home).audit()

    assert report["status"] == "warnings"
    assert report["counts"]["ready_prompts"] == 0
    assert any(issue["kind"] == "weak_prompt_contract" for issue in report["issues"])


def test_prompt_proposal_generates_concise_prompt_not_contract_template(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")

    proposal = PromptProposalModule(home=home).propose(
        AddPromptRequest(
            title="Review exported notes",
            content="Check exported Apple Notes content for missing details, cramped formatting, and stale deleted records before publishing.",
        )
    )

    content = proposal["request"]["content"]
    assert content.startswith("Review the current change")
    assert "Return:" in content
    assert "用于：" not in content
    assert "做法：" not in content
    assert "输出：" not in content
    assert "Role and Purpose" not in content
    assert "Source Material To Preserve" not in content


def test_prompt_proposal_content_is_copy_ready_not_metadata_card(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")

    proposal = PromptProposalModule(home=home).propose(
        AddPromptRequest(
            title="Selective AI Eval Planning",
            content=(
                "Ai eval 自动化越多，经常要回归测试，就越慢，看看怎么优化规则，"
                "会智能的在需要的时候根据需求选择相应的AI eval吗，而不是每次的全量吗"
            ),
            description="Select focused AI eval and smoke coverage based on change risk.",
            use_cases=["Plan regression verification with expensive AI eval suites"],
            outputs=["selected suites", "commands", "rationale", "skipped checks"],
            kind="eval_prompt",
            domain="testing",
            intent="audit",
        )
    )

    content = proposal["request"]["content"]
    assert "用于：" not in content
    assert "触发：" not in content
    assert "输出：" not in content
    assert "边界：" not in content
    assert content.startswith("Review the current change")
    assert "Return:" in content
    assert "selected_suites" in content
    assert proposal["request"]["triggers"]
    assert proposal["request"]["outputs"] == [
        "selected suites",
        "commands",
        "rationale",
        "skipped checks",
    ]


def test_prompt_proposal_preserves_title_commitments_for_hardening(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")

    proposal = PromptProposalModule(home=home).propose(
        AddPromptRequest(
            title="Delivery Verification Rerun Hardening",
            content=(
                "AI eval automation can make regression testing slow. Select focused suites "
                "based on the change and preserve useful checks for future runs."
            ),
            description="Verify delivery, choose focused evals, and harden useful checks.",
            use_cases=["Before reporting a change as done"],
            kind="eval_prompt",
            domain="testing",
            intent="audit",
        )
    )

    content = proposal["request"]["content"].casefold()
    outputs = proposal["request"]["outputs"]

    assert "harden" in content
    assert "future" in content
    assert "regression" in content
    assert "rerun" in content
    assert "change boundary" in content
    assert "pass/fail" in content
    assert "hardened_assets" in content
    assert "rerun_instructions" in content
    assert "hardened_assets" in outputs
    assert "rerun_instructions" in outputs
    assert proposal["evaluation"]["checks"]["professional_contract"] is True
    assert proposal["evaluation"]["checks"]["prompt_ai_eval"] == "pass"
    assert [item["name"] for item in proposal["evaluation"]["prompt_ai_eval"]["rounds"]] == [
        "professional_quality",
        "adversarial_reuse",
    ]


def test_prompt_proposal_can_request_optional_external_ai_eval(
    tmp_path,
    monkeypatch,
):
    home = AlcoveHome.init(tmp_path / "home")
    calls: list[dict[str, str]] = []

    def fake_external_eval(prompt, *, provider, cwd):  # type: ignore[no-untyped-def]
        calls.append({"provider": provider, "title": prompt.title, "cwd": str(cwd)})
        return {
            "status": "completed",
            "provider": provider,
            "review": {
                "verdict": "pass",
                "score": 0.91,
                "rounds": [],
                "must_fix": [],
                "suggestions": [],
            },
        }

    monkeypatch.setattr(
        "alcove.prompt_proposals.run_external_prompt_ai_eval",
        fake_external_eval,
    )

    proposal = PromptProposalModule(home=home).propose(
        AddPromptRequest(
            title="Prompt Library Quality Review",
            content=(
                "Review a candidate prompt before it enters the prompt library. "
                "Check whether the body is directly reusable, concise, free of "
                "metadata-card headings, and backed by clear evidence. Return the "
                "verdict, required fixes, suggested merge target, and final copy-ready "
                "prompt text."
            ),
            description="Review and improve prompt-library candidates before saving.",
            outputs=["verdict", "required fixes", "copy-ready prompt"],
            kind="eval_prompt",
            domain="prompt-library",
            intent="audit",
        ),
        ai_eval_provider="codex",
    )

    assert calls == [
        {
            "provider": "codex",
            "title": "Prompt Library Quality Review",
            "cwd": str(Path.cwd()),
        }
    ]
    assert proposal["evaluation"]["checks"]["external_prompt_ai_eval"] == "completed"
    assert proposal["evaluation"]["external_prompt_ai_eval"]["provider"] == "codex"


def test_prompt_proposal_allows_short_source_after_successful_curation(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")

    proposal = PromptProposalModule(home=home).propose(
        AddPromptRequest(
            title="AI Eval Selection Strategy",
            content=(
                "Ai eval 自动化越多，经常要回归测试，就越慢，看看怎么优化规则，"
                "会智能的在需要的时候根据需求选择相应的AI eval吗，而不是每次的全量吗"
            ),
        )
    )

    assert proposal["action"] == "create_new"
    assert proposal["evaluation"]["verdict"] == "ready"
    assert "source_too_short" in proposal["warnings"]
    assert proposal["evaluation"]["checks"]["prompt_ai_eval"] == "pass"
    assert proposal["evaluation"]["checks"]["external_prompt_ai_eval"] == "skipped"
    assert proposal["request"]["content"].startswith("Review the current change")
    assert "Return:" in proposal["request"]["content"]


def test_prompt_proposal_rewrites_metadata_card_input_to_copy_ready_prompt(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")

    proposal = PromptProposalModule(home=home).propose(
        AddPromptRequest(
            title="Prompt Library Write Review",
            content=(
                "用于：添加新 prompt 前做质量审查。\n\n"
                "触发：用户说想保存提示词。\n\n"
                "输出：可保存的提示词、相似项、合并建议。\n\n"
                "边界：不要把一次性对话直接保存。"
            ),
            kind="eval_prompt",
            domain="prompt-library",
            intent="audit",
        )
    )

    content = proposal["request"]["content"]
    assert content.startswith("Review the current change")
    assert "Return:" in content
    assert "用于：" not in content
    assert "触发：" not in content
    assert "边界：" not in content


def test_prompt_proposal_removes_chat_fragments_from_optimized_content(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")

    proposal = PromptProposalModule(home=home).propose(
        AddPromptRequest(
            title="Short Command Continuation",
            content=(
                "我经常用一两个字推进任务。\n"
                "- 继续 = 接着上次的工作做下去，不要重新解释。\n"
                "- 做完了吗 = 做完了就一句话报；没做完就一句话报进度。\n"
                "- 提交吧 = 直接 git commit。\n"
                "卡住的时候一句话说什么卡住。"
            ),
        )
    )

    content = proposal["request"]["content"]
    assert proposal["action"] == "save_as_knowledge_note_not_prompt"
    assert proposal["evaluation"]["verdict"] == "reject"
    assert "我经常用一两个字" not in content
    assert "原始要点" not in content
    assert "继续 =" not in content
    assert "提交吧" not in content


def test_prompt_save_rejects_unready_proposal_by_default(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    proposal = PromptProposalModule(home=home).propose(
        AddPromptRequest(
            title="Vague Prompt",
            content="继续就继续做，提交就提交，别解释。",
        )
    )

    try:
        PromptProposalModule(home=home).request_from_proposal(proposal["id"])
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("unready prompt proposal should not be saveable")

    assert "not ready" in message or "recommends" in message
    assert PromptsModule(home=home).list(status="") == []


def test_prompt_save_from_update_proposal_merges_with_existing_prompt(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    prompts = PromptsModule(home=home)
    prompts.save(
        AddPromptRequest(
            title="Delivery Verification",
            content=(
                "Before claiming delivery is complete, run the relevant checks and report "
                "the exact evidence. Include residual risks and do not claim unrun checks passed."
            ),
            description="Verify delivery before reporting completion.",
            tags=["verification"],
            use_cases=["Final delivery verification"],
            triggers=["done", "ready to ship"],
            outputs=["checks", "evidence", "risks"],
            kind="eval_prompt",
            domain="testing",
            intent="audit",
            quality={"score": 0.9},
        )
    )
    proposal = PromptProposalModule(home=home).propose(
        AddPromptRequest(
            title="Selective AI Eval Planning",
            content=(
                "When regression checks are expensive, choose focused AI eval suites "
                "based on changed modules, qualitative risk, and recent failures. "
                "Return selected suites, commands, skipped checks, and escalation conditions."
            ),
            description="Select focused AI eval and smoke coverage based on change risk.",
            tags=["eval"],
            use_cases=["Plan regression verification with expensive AI eval suites"],
            triggers=["which ai eval should run"],
            outputs=["selected suites", "commands", "skipped checks", "escalation conditions"],
            kind="eval_prompt",
            domain="testing",
            intent="audit",
        )
    )

    request = PromptProposalModule(home=home).request_from_proposal(proposal["id"])
    saved = prompts.save(request)
    prompt = prompts.get("delivery-verification")

    assert proposal["action"] == "update_existing"
    assert saved.prompt.id == "delivery-verification"
    assert "Before claiming delivery is complete" in prompt.content
    assert "choose focused AI eval suites" in prompt.content
    assert "which ai eval should run" in prompt.triggers
    assert "selected suites" in prompt.outputs
    assert {"eval", "eval-prompt", "testing", "verification"}.issubset(set(prompt.tags))


def test_prompt_curation_keeps_style_prompts_as_source_notes(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    source = tmp_path / "style_prompts.md"
    source.write_text(
        """# Style Prompts

## 1. debugging — 排错

**可粘贴 prompt 片段**:
```
排错请先复现，再定位根因，最后做最小修复并验证。
不要吞异常，不要跳过校验，失败两次后停下来分析。
```
""",
        encoding="utf-8",
    )

    curation = PromptCurationModule(home=home)
    scan = curation.scan([source])
    candidates = curation.list_candidates(min_score=0.5)
    promoted = curation.promote(min_score=0.8)
    prompts = PromptsModule(home=home).search("复现")

    assert scan["count"] == 1
    assert candidates[0].kind == "source_note"
    assert promoted["count"] == 0
    assert prompts == []


def test_prompt_save_infers_use_cases_when_omitted(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    module = PromptsModule(home=home)

    result = module.save(
        AddPromptRequest(
            title="Debug Root Cause",
            content="Diagnose the failure before patching.",
            description="Find the root cause of a bug.",
            tags=["debug"],
        )
    )

    doc = MarkdownRepository().read_doc(result.path)
    prompt = module.get("debug-root-cause")

    assert doc.frontmatter["use_cases"] == ["Debugging"]
    assert prompt.use_cases == ["Debugging"]


def test_search_includes_active_prompts(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    PromptsModule(home=home).save(
        AddPromptRequest(
            title="Review Prompt",
            content="Check edge cases and missing tests.",
            tags=["review"],
        )
    )

    rows = SearchModule(home=home).search(SearchRequest(query="edge cases", type_filter="Prompt"))

    assert rows[0]["root"] == "prompts"
    assert rows[0]["type"] == "Prompt"
    assert rows[0]["title"] == "Review Prompt"
    assert rows[0]["tags"] == ["review"]
    assert rows[0]["path"] == "prompts/review-prompt.md"


def test_prompt_search_rebuilds_stale_index_from_okf_markdown(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    module = PromptsModule(home=home)
    path = home.paths().prompts / "manual-prompt.md"
    MarkdownRepository().write_doc(
        path,
        MarkdownDoc(
            frontmatter={
                "type": "Prompt",
                "schema": "okf/prompt/v1",
                "title": "Manual Prompt",
                "description": "Manual prompt description.",
                "tags": ["manual"],
                "status": "active",
                "use_cases": ["manual testing"],
                "source_refs": [],
                "created_at": "2026-07-09T00:00:00+00:00",
                "updated_at": "2026-07-09T00:00:00+00:00",
            },
            body="# Manual Prompt\n\n## Prompt\n\nFind manual index needle.\n",
        ),
    )

    matches = module.search("manual index needle")
    index = json.loads((home.paths().prompts / "index.json").read_text(encoding="utf-8"))

    assert [prompt.title for prompt in matches] == ["Manual Prompt"]
    assert index["count"] == 1
    assert index["prompts"][0]["id"] == "manual-prompt"


def test_prompt_rebuild_index_rejects_non_okf_prompt_markdown(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    path = home.paths().prompts / "broken.md"
    path.write_text(
        "---\ntype: Prompt\ntitle: Broken\n---\n# Broken\n\n## Prompt\n\nMissing schema.\n",
        encoding="utf-8",
    )

    try:
        PromptsModule(home=home).rebuild_index()
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected invalid prompt frontmatter to fail index rebuild")

    assert "missing required fields" in message
    assert "schema" in message
