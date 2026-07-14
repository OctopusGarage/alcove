from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from alcove.home import AlcoveHome
from alcove.prompt_text import STOP_TOKENS, prompt_tokens
from alcove.prompts import Prompt, PromptsModule
from alcove.workspace import Workspace


MIN_RECOMMENDATION_SCORE = 0.18
SINGLE_INTENT_RELATIVE_CUTOFF = 0.68
MULTI_INTENT_RELATIVE_CUTOFF = 0.42
BEHAVIOR_MAPPING_MARKERS = (
    "我说",
    "当我说",
    "用户说",
    "短指令",
    "自动理解",
    "映射",
)
BEHAVIOR_MAPPING_ACTIONS = (
    "继续",
    "推送",
    "提交",
    "做完了吗",
    "好了吗",
)
MULTI_INTENT_MARKERS = (
    "包括",
    "以及",
    "同时",
    "并且",
    "还有",
)


@dataclass(frozen=True)
class PromptRecommendation:
    prompt: Prompt
    score: float
    reasons: list[str]


class PromptRecommendationModule:
    def __init__(self, workspace: Workspace | None = None, home: AlcoveHome | None = None) -> None:
        self.prompts = PromptsModule(workspace=workspace, home=home)

    def recommend(
        self,
        scenario: str,
        *,
        limit: int = 5,
        status: str = "active",
        surface: str = "",
    ) -> list[PromptRecommendation]:
        if _looks_like_behavior_mapping(scenario):
            return []
        scenario_tokens = _tokens(scenario)
        recommendations: list[PromptRecommendation] = []
        for prompt in self.prompts.list(status=status):
            if surface and prompt.surfaces and surface not in prompt.surfaces:
                continue
            score, reasons = self._score(prompt, scenario, scenario_tokens)
            if score < MIN_RECOMMENDATION_SCORE:
                continue
            recommendations.append(
                PromptRecommendation(prompt=prompt, score=round(score, 4), reasons=reasons)
            )
        recommendations.sort(key=lambda item: (-item.score, item.prompt.title))
        return _trim_recommendations(
            recommendations,
            limit=max(1, limit),
            multi_intent=_looks_multi_intent(scenario),
        )

    def _score(
        self, prompt: Prompt, scenario: str, scenario_tokens: set[str]
    ) -> tuple[float, list[str]]:
        reasons: list[str] = []
        weighted_fields = [
            ("title", prompt.title, 4.0),
            ("description", prompt.description, 3.0),
            ("intent", prompt.intent, 3.0),
            ("domain", prompt.domain, 2.5),
            ("triggers", " ".join(prompt.triggers), 2.5),
            ("use cases", " ".join(prompt.use_cases), 2.0),
            ("tags", " ".join(prompt.tags), 1.5),
            ("content", prompt.content, 0.5),
        ]
        raw_score = 0.0
        for label, value, weight in weighted_fields:
            matches = scenario_tokens & _tokens(value)
            if not matches:
                continue
            contribution = min(len(matches), 6) * weight
            raw_score += contribution
            sample = ", ".join(_sample_matches(matches))
            reasons.append(f"{label} matched: {sample}")

        for trigger in prompt.triggers:
            normalized_trigger = trigger.casefold().strip()
            if (
                normalized_trigger
                and normalized_trigger not in STOP_TOKENS
                and normalized_trigger in scenario.casefold()
            ):
                raw_score += 3.0
                reasons.append(f"explicit trigger: {trigger}")

        quality_score = prompt.quality.get("score")
        if isinstance(quality_score, int | float):
            raw_score *= 0.75 + (float(quality_score) * 0.5)
            if float(quality_score) >= 0.8:
                reasons.append("curated quality score")

        if prompt.kind == "source_note":
            raw_score *= 0.4
        elif prompt.kind in {"fragment", "modifier"}:
            raw_score *= 0.9
        elif prompt.kind in {"full_prompt", "playbook", "eval_prompt"}:
            raw_score *= 1.1

        normalized = min(raw_score / 20.0, 1.0)
        return normalized, reasons[:5]


def recommendation_dict(item: PromptRecommendation) -> dict[str, Any]:
    prompt = item.prompt
    return {
        "score": item.score,
        "reasons": item.reasons,
        "prompt": {
            "id": prompt.id,
            "title": prompt.title,
            "description": prompt.description,
            "kind": prompt.kind,
            "domain": prompt.domain,
            "intent": prompt.intent,
            "tags": prompt.tags,
            "use_cases": prompt.use_cases,
            "surfaces": prompt.surfaces,
            "path": f"prompts/{prompt.path.name}",
        },
    }


def _tokens(value: str) -> set[str]:
    return prompt_tokens(value)


def _looks_like_behavior_mapping(value: str) -> bool:
    text = str(value or "").casefold()
    return any(marker in text for marker in BEHAVIOR_MAPPING_MARKERS) and any(
        action in text for action in BEHAVIOR_MAPPING_ACTIONS
    )


def _looks_multi_intent(value: str) -> bool:
    text = str(value or "").casefold()
    return any(marker in text for marker in MULTI_INTENT_MARKERS)


def _trim_recommendations(
    recommendations: list[PromptRecommendation], *, limit: int, multi_intent: bool
) -> list[PromptRecommendation]:
    if not recommendations:
        return []
    top_score = recommendations[0].score
    relative_cutoff = (
        MULTI_INTENT_RELATIVE_CUTOFF if multi_intent else SINGLE_INTENT_RELATIVE_CUTOFF
    )
    cutoff = max(MIN_RECOMMENDATION_SCORE, round(top_score * relative_cutoff, 4))
    return [item for item in recommendations if item.score >= cutoff][:limit]


def _sample_matches(matches: set[str]) -> list[str]:
    samples: list[str] = []
    for token in sorted(matches, key=lambda item: (-len(item), item)):
        if any(token in sample for sample in samples):
            continue
        samples.append(token)
        if len(samples) >= 4:
            break
    return samples
