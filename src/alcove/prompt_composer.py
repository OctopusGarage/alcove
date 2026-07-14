from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from alcove.home import AlcoveHome
from alcove.paths import compact_user_path
from alcove.prompt_recommendation import PromptRecommendationModule
from alcove.prompts import Prompt
from alcove.workspace import Workspace


@dataclass(frozen=True)
class ComposedPromptSource:
    prompt: Prompt
    score: float
    reasons: list[str]
    included_chars: int
    truncated: bool


@dataclass(frozen=True)
class ComposedPrompt:
    scenario: str
    prompt: str
    sources: list[ComposedPromptSource]
    warnings: list[str]


class PromptComposerModule:
    """Build a ready-to-use prompt pack from reusable prompt records."""

    def __init__(self, workspace: Workspace | None = None, home: AlcoveHome | None = None) -> None:
        self.recommender = PromptRecommendationModule(workspace=workspace, home=home)

    def compose(
        self,
        scenario: str,
        *,
        limit: int = 4,
        status: str = "active",
        surface: str = "",
        max_chars_per_prompt: int = 1800,
    ) -> ComposedPrompt:
        clean_scenario = " ".join(str(scenario or "").split())
        recommendations = self.recommender.recommend(
            clean_scenario,
            limit=max(1, limit),
            status=status,
            surface=surface,
        )
        sources: list[ComposedPromptSource] = []
        warnings: list[str] = []
        for recommendation in recommendations:
            content = recommendation.prompt.content.strip()
            truncated = len(content) > max_chars_per_prompt
            sources.append(
                ComposedPromptSource(
                    prompt=recommendation.prompt,
                    score=recommendation.score,
                    reasons=recommendation.reasons,
                    included_chars=min(len(content), max_chars_per_prompt),
                    truncated=truncated,
                )
            )
            if truncated:
                warnings.append(
                    f"Prompt {recommendation.prompt.id} was truncated in the composed pack."
                )
        if not sources:
            warnings.append(
                "No matching prompt records were found; generated a minimal scenario prompt."
            )
        return ComposedPrompt(
            scenario=clean_scenario,
            prompt=self._render(
                clean_scenario,
                sources,
                surface=surface,
                max_chars_per_prompt=max_chars_per_prompt,
            ),
            sources=sources,
            warnings=warnings,
        )

    def _render(
        self,
        scenario: str,
        sources: list[ComposedPromptSource],
        *,
        surface: str,
        max_chars_per_prompt: int,
    ) -> str:
        lines = [
            "# Alcove Prompt Pack",
            "",
            "## Scenario",
            "",
            scenario or "Use the selected reusable prompts to complete the current task.",
            "",
            "## Operating Instructions",
            "",
            "- Treat the selected prompt records as reusable guidance, not as immutable output.",
            "- Prefer the most relevant source guidance first when instructions overlap.",
            "- Preserve user intent, concrete constraints, and requested verification steps.",
            "- If the task involves durable user data, use the appropriate governed CLI/MCP write path.",
            "- State assumptions and verification results explicitly.",
        ]
        if surface:
            lines.append(f"- Target execution surface: `{surface}`.")
        lines.extend(["", "## Selected Prompt Guidance", ""])
        if not sources:
            lines.extend(
                [
                    "No matching prompt records were found. Proceed with a concise, evidence-led prompt:",
                    "",
                    "- Clarify the goal.",
                    "- Inspect relevant local context.",
                    "- Propose or implement the smallest reliable change.",
                    "- Verify the result and report residual risks.",
                ]
            )
        for index, source in enumerate(sources, start=1):
            prompt = source.prompt
            lines.extend(
                [
                    f"### {index}. {prompt.title}",
                    "",
                    f"- Library id: `{prompt.id}`",
                    f"- Kind: `{prompt.kind}`",
                    f"- Score: `{source.score:.2f}`",
                    f"- Why selected: {', '.join(source.reasons) if source.reasons else 'semantic match'}",
                ]
            )
            if prompt.domain or prompt.intent:
                lines.append(
                    f"- Domain/intent: `{prompt.domain or 'general'}` / `{prompt.intent or 'general'}`"
                )
            if prompt.use_cases:
                lines.append(f"- Use cases: {', '.join(prompt.use_cases)}")
            if prompt.outputs:
                lines.append(f"- Expected outputs: {', '.join(prompt.outputs)}")
            lines.extend(
                [
                    "",
                    "```text",
                    self._excerpt(prompt.content, max_chars_per_prompt),
                    "```",
                    "",
                ]
            )
        lines.extend(
            [
                "## Final Task",
                "",
                "Using the scenario and selected guidance above, produce the best next response or execution plan for the current user request.",
                "If implementation is appropriate, carry it through verification before reporting back.",
            ]
        )
        return "\n".join(lines).strip() + "\n"

    def _excerpt(self, content: str, max_chars: int) -> str:
        clean = str(content or "").strip()
        if len(clean) <= max_chars:
            return clean
        return (
            clean[: max(0, max_chars)].rstrip() + "\n\n[truncated; call prompt get for full text]"
        )


def composed_prompt_dict(item: ComposedPrompt) -> dict[str, Any]:
    return {
        "scenario": item.scenario,
        "prompt": item.prompt,
        "warnings": item.warnings,
        "sources": [
            {
                "id": source.prompt.id,
                "title": source.prompt.title,
                "kind": source.prompt.kind,
                "domain": source.prompt.domain,
                "intent": source.prompt.intent,
                "score": source.score,
                "reasons": source.reasons,
                "path": compact_user_path(source.prompt.path),
                "included_chars": source.included_chars,
                "truncated": source.truncated,
            }
            for source in item.sources
        ],
    }
