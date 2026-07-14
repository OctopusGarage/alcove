from __future__ import annotations

from typing import Any


def prompt_record_quality_score(prompt: Any, *, default_kind: str = "full_prompt") -> float:
    score = 0.0
    if len(prompt.content.strip()) >= 200:
        score += 0.2
    elif len(prompt.content.strip()) >= 80:
        score += 0.1
    if prompt.description.strip():
        score += 0.15
    if prompt.use_cases:
        score += 0.15
    if prompt.tags:
        score += 0.1
    if prompt.kind and prompt.kind != default_kind:
        score += 0.1
    if prompt.domain:
        score += 0.1
    if prompt.intent:
        score += 0.05
    if prompt.surfaces:
        score += 0.05
    if prompt.triggers:
        score += 0.05
    if prompt.outputs:
        score += 0.05
    if prompt.source_refs:
        score += 0.05
    existing_score = prompt.quality.get("score")
    if isinstance(existing_score, int | float):
        score = max(score, min(float(existing_score), 1.0))
    if prompt.kind == "style_profile":
        score = min(score, 0.74)
    if not has_professional_contract(prompt):
        score = min(score, 0.74)
    return round(min(score, 1.0), 3)


def proposal_quality_score(
    content: str,
    description: str,
    use_cases: list[str],
    outputs: list[str],
) -> float:
    score = 0.35
    if len(content) >= 160:
        score += 0.2
    if description:
        score += 0.15
    if use_cases:
        score += 0.15
    if outputs:
        score += 0.15
    return round(min(score, 0.95), 2)


def has_professional_contract(prompt: Any) -> bool:
    title = str(getattr(prompt, "title", "") or "")
    description = str(getattr(prompt, "description", "") or "")
    content = str(getattr(prompt, "content", "") or "")
    text = f"{title}\n{description}\n{content}".casefold()
    weak_phrases = [
        "我经常用一两个字",
        "从历史 ai 输入中提炼",
        "场景交互规则。",
        "可粘贴 prompt 片段",
        "source material to preserve",
        "act as an intent interpreter",
    ]
    if any(phrase in text for phrase in weak_phrases):
        return False
    action_signals = [
        "review",
        "check",
        "verify",
        "rewrite",
        "extract",
        "design",
        "run",
        "report",
        "检查",
        "验证",
        "整理",
        "输出",
        "报告",
        "执行",
        "改",
        "跑",
        "读",
        "不要",
    ]
    reuse_signals = [
        "when",
        "trigger",
        "use",
        "output",
        "risk",
        "evidence",
        "用在",
        "触发",
        "场景",
        "输出",
        "证据",
        "风险",
        "边界",
    ]
    action_score = sum(1 for signal in action_signals if signal in text)
    reuse_score = sum(1 for signal in reuse_signals if signal in text)
    line_count = sum(1 for line in prompt.content.splitlines() if line.strip())
    sentence_count = sum(
        1
        for sentence in (
            prompt.content.replace("。", ".")
            .replace("！", ".")
            .replace("？", ".")
            .replace(";", ".")
            .replace("；", ".")
            .split(".")
        )
        if sentence.strip()
    )
    instruction_units = max(line_count, sentence_count)
    boilerplate_headings = sum(
        1
        for heading in [
            "role and purpose",
            "required inputs",
            "operating rules",
            "output contract",
            "guardrails and stop conditions",
        ]
        if heading in text
    )
    if boilerplate_headings >= 4:
        return False
    if not _title_commitments_are_satisfied(title, content):
        return False
    score = action_score + reuse_score
    if prompt.kind in {"modifier", "style_profile", "fragment"}:
        return score >= 4 and instruction_units >= 3
    return score >= 5 and instruction_units >= 4


def _title_commitments_are_satisfied(title: str, content: str) -> bool:
    title_text = str(title or "").casefold()
    content_text = str(content or "").casefold()
    checks = [
        (
            ("verify", "verification", "验证", "校验", "交付"),
            ("verify", "verification", "evidence", "checked", "验证", "校验", "证据"),
        ),
        (
            ("rerun", "re-run", "复跑", "重跑", "再次运行"),
            ("rerun", "re-run", "repeat", "command", "commands", "复跑", "重跑", "命令"),
        ),
        (
            ("harden", "hardening", "solidify", "codify", "固化", "沉淀"),
            (
                "harden",
                "hardened",
                "regression",
                "future",
                "codify",
                "reusable",
                "固化",
                "沉淀",
                "回归",
                "后续",
            ),
        ),
    ]
    for title_tokens, required_tokens in checks:
        if any(token in title_text for token in title_tokens) and not any(
            token in content_text for token in required_tokens
        ):
            return False
    return True
