from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from alcove.home import AlcoveHome
from alcove.markdown import normalize_slug
from alcove.paths import compact_user_path
from alcove.prompt_ai_eval import (
    configured_prompt_ai_eval_provider,
    evaluate_prompt_candidate,
    run_external_prompt_ai_eval,
)
from alcove.prompt_recommendation import PromptRecommendationModule, recommendation_dict
from alcove.prompt_quality import has_professional_contract, proposal_quality_score
from alcove.prompt_text import ordered_prompt_tokens, prompt_similarity_fingerprint
from alcove.prompts import AddPromptRequest, Prompt, PromptsModule
from alcove.runtime import AlcoveRuntime
from alcove.workspace import Workspace


@dataclass(frozen=True)
class PromptProposal:
    id: str
    status: str
    action: str
    title: str
    request: AddPromptRequest
    similar: list[dict[str, Any]]
    warnings: list[str]
    rationale: list[str]
    evaluation: dict[str, Any]
    path: Path


class PromptProposalModule:
    """Prepare prompt writes before committing them to the active library."""

    def __init__(self, workspace: Workspace | None = None, home: AlcoveHome | None = None) -> None:
        self.runtime = AlcoveRuntime.from_modules(workspace=workspace, home=home)
        self.root = self.runtime.prompts_root / "proposals"
        self.prompts = PromptsModule(workspace=workspace, home=home)

    def propose(
        self,
        request: AddPromptRequest,
        *,
        ai_eval_provider: str = "",
    ) -> dict[str, Any]:
        curated = self._curated_request(request)
        similar = [
            recommendation_dict(item)
            for item in PromptRecommendationModule(
                self.runtime.workspace,
                home=self.runtime.home,
            ).recommend(
                self._scenario(curated),
                limit=5,
                status="active",
                surface=(curated.surfaces[0] if curated.surfaces else ""),
            )
        ]
        exact_duplicate = self._exact_duplicate(curated)
        warnings = self._warnings(curated)
        action = self._action(curated, similar, exact_duplicate, warnings)
        rationale = self._rationale(action, similar, exact_duplicate, warnings)
        if exact_duplicate and not any(
            item["prompt"]["id"] == exact_duplicate["id"] for item in similar
        ):
            similar.insert(
                0, {"score": 1.0, "reasons": ["exact content duplicate"], "prompt": exact_duplicate}
            )
        proposal_id = self._proposal_id(curated)
        proposal = PromptProposal(
            id=proposal_id,
            status="proposed",
            action=action,
            title=curated.title,
            request=curated,
            similar=similar[:5],
            warnings=warnings,
            rationale=rationale,
            evaluation=self._evaluation(
                curated,
                action,
                similar,
                exact_duplicate,
                warnings,
                ai_eval_provider=ai_eval_provider,
            ),
            path=self.root / f"{proposal_id}.json",
        )
        self._write(proposal)
        return proposal_dict(proposal)

    def get(self, proposal_id: str) -> dict[str, Any]:
        return proposal_dict(self._read(proposal_id))

    def request_from_proposal(self, proposal_id: str) -> AddPromptRequest:
        proposal = self._read(proposal_id)
        if proposal.action in {
            "reject_as_one_off",
            "save_as_knowledge_note_not_prompt",
            "merge_into_existing",
        }:
            raise ValueError(
                f"Prompt proposal {proposal.id} recommends {proposal.action}; "
                "use --force only after explicitly deciding this belongs in the prompt library."
            )
        verdict = str(proposal.evaluation.get("verdict") or "")
        if verdict not in {"ready", "update_existing"}:
            raise ValueError(
                f"Prompt proposal {proposal.id} is not ready for the prompt library "
                f"(verdict: {verdict or 'unknown'}). Review or force-save only after "
                "explicitly deciding the optimized prompt is reusable."
            )
        if proposal.action == "update_existing" and proposal.similar:
            target = proposal.similar[0].get("prompt") or {}
            target_title = str(target.get("title") or "")
            if target_title:
                try:
                    existing = self.prompts.get(target.get("id") or target_title)
                except (FileNotFoundError, ValueError):
                    return replace(proposal.request, title=target_title)
                return _merge_prompt_request(existing, proposal.request, target_title=target_title)
        return proposal.request

    def _curated_request(self, request: AddPromptRequest) -> AddPromptRequest:
        title = self._clean_title(request.title, request.content)
        raw_content = self._clean_content(request.content)
        source_warnings = _source_warnings(raw_content)
        content = raw_content
        kind = request.kind if request.kind != "full_prompt" else self._infer_kind(title, content)
        domain = request.domain or self._infer_domain(title, content)
        intent = request.intent or self._infer_intent(title, content, kind)
        tags = _unique([*request.tags, *self._suggested_tags(domain, intent, kind)])
        use_cases = request.use_cases or [self._use_case(title, domain, intent)]
        description = request.description.strip() or self._description(title, kind, domain, intent)
        commitments = _semantic_commitments(title, f"{content}\n{description}")
        outputs = _augment_outputs(request.outputs or self._outputs(kind, intent), commitments)
        triggers = request.triggers or (
            [title] if source_warnings else self._triggers(title, content)
        )
        inputs = request.inputs or ["goal", "context", "constraints"]
        surfaces = request.surfaces or ["codex", "claude-code", "generic-llm"]
        content = self._professional_content(
            title=title,
            content=content,
            kind=kind,
            domain=domain,
            intent=intent,
            use_cases=use_cases,
            triggers=triggers,
            inputs=inputs,
            outputs=outputs,
            commitments=commitments,
        )
        quality = {
            **request.quality,
            "status": request.quality.get("status") or "proposed",
            "score": request.quality.get("score")
            or self._quality_score(content, description, use_cases, outputs),
        }
        if source_warnings:
            quality["source_warnings"] = source_warnings
        return AddPromptRequest(
            title=title,
            content=content,
            description=description,
            tags=tags,
            use_cases=use_cases,
            source_refs=_clean_source_refs(request.source_refs),
            kind=kind,
            domain=domain,
            intent=intent,
            surfaces=surfaces,
            triggers=triggers,
            inputs=inputs,
            outputs=outputs,
            quality=quality,
        )

    def _exact_duplicate(self, request: AddPromptRequest) -> dict[str, Any] | None:
        target = _fingerprint(request.content)
        if not target:
            return None
        for prompt in self.prompts.list(status="active"):
            if _fingerprint(prompt.content) == target:
                return {
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
                }
        return None

    @staticmethod
    def _action(
        request: AddPromptRequest,
        similar: list[dict[str, Any]],
        exact_duplicate: dict[str, Any] | None,
        warnings: list[str],
    ) -> str:
        if exact_duplicate:
            return "merge_into_existing"
        if (
            "looks_like_chat_fragment" in warnings
            or "looks_like_historical_interaction_rule" in warnings
        ):
            return "save_as_knowledge_note_not_prompt"
        if "looks_like_article_or_note" in warnings:
            return "save_as_knowledge_note_not_prompt"
        if len(request.content.strip()) < 80:
            return "reject_as_one_off"
        if similar and float(similar[0].get("score") or 0) >= 0.72:
            return "update_existing"
        if similar and float(similar[0].get("score") or 0) >= 0.45:
            return "create_new_after_review"
        return "create_new"

    @staticmethod
    def _rationale(
        action: str,
        similar: list[dict[str, Any]],
        exact_duplicate: dict[str, Any] | None,
        warnings: list[str],
    ) -> list[str]:
        rationale = [f"recommended action: {action}"]
        if exact_duplicate:
            rationale.append(f"exact duplicate content: {exact_duplicate['title']}")
        if similar:
            top = similar[0]["prompt"]
            rationale.append(f"top similar prompt: {top['title']} ({similar[0]['score']:.2f})")
        if warnings:
            rationale.append("warnings: " + ", ".join(warnings))
        if action.startswith("create_new"):
            rationale.append("no high-confidence duplicate blocks a new reusable prompt")
        return rationale

    def _evaluation(
        self,
        request: AddPromptRequest,
        action: str,
        similar: list[dict[str, Any]],
        exact_duplicate: dict[str, Any] | None,
        warnings: list[str],
        *,
        ai_eval_provider: str = "",
    ) -> dict[str, Any]:
        findings: list[str] = []
        score = float(request.quality.get("score") or 0.0)
        if warnings:
            findings.extend(warnings)
        blocking_warnings = [warning for warning in warnings if warning != "source_too_short"]
        if exact_duplicate:
            findings.append("exact_duplicate")
        professional_contract = has_professional_contract(request)
        ai_eval = evaluate_prompt_candidate(request)
        provider = ai_eval_provider or configured_prompt_ai_eval_provider(
            self.runtime.home.load_config() if self.runtime.home else {}
        )
        external_ai_eval = run_external_prompt_ai_eval(
            request,
            provider=provider,
            cwd=Path.cwd(),
        )
        if not professional_contract:
            findings.append("weak_prompt_contract")
        if ai_eval["verdict"] != "pass":
            findings.append("prompt_ai_eval_needs_revision")
        external_status = str(external_ai_eval.get("status") or "")
        external_review = external_ai_eval.get("review")
        external_verdict = (
            str(external_review.get("verdict") or "").casefold()
            if isinstance(external_review, dict)
            else ""
        )
        if external_status == "completed" and external_verdict not in {
            "accept",
            "pass",
            "approved",
            "ready",
        }:
            findings.append("external_prompt_ai_eval_needs_revision")
        elif external_status == "error":
            findings.append("external_prompt_ai_eval_error")
        if similar:
            top = similar[0]
            top_prompt = top.get("prompt") or {}
            findings.append(
                f"top_similar:{top_prompt.get('id', 'unknown')}:{float(top.get('score') or 0):.2f}"
            )
        if action in {"reject_as_one_off", "save_as_knowledge_note_not_prompt"}:
            verdict = "reject"
        elif action == "merge_into_existing":
            verdict = "merge_required"
        elif (
            action == "update_existing"
            and professional_contract
            and ai_eval["verdict"] == "pass"
            and "external_prompt_ai_eval_needs_revision" not in findings
            and "external_prompt_ai_eval_error" not in findings
        ):
            verdict = "update_existing"
        elif (
            score >= 0.75
            and not blocking_warnings
            and professional_contract
            and ai_eval["verdict"] == "pass"
            and "external_prompt_ai_eval_needs_revision" not in findings
            and "external_prompt_ai_eval_error" not in findings
        ):
            verdict = "ready"
        else:
            verdict = "needs_review"
        return {
            "verdict": verdict,
            "score": round(score, 2),
            "action": action,
            "findings": findings,
            "checks": {
                "curated_content": bool(request.content.strip()),
                "has_description": bool(request.description.strip()),
                "has_use_cases": bool(request.use_cases),
                "has_outputs": bool(request.outputs),
                "dedupe_checked": True,
                "similar_count": len(similar),
                "professional_contract": professional_contract,
                "prompt_ai_eval": ai_eval["verdict"],
                "external_prompt_ai_eval": external_status,
                "source_warnings": list(request.quality.get("source_warnings") or []),
            },
            "prompt_ai_eval": ai_eval,
            "external_prompt_ai_eval": external_ai_eval,
        }

    @staticmethod
    def _scenario(request: AddPromptRequest) -> str:
        return " ".join(
            [
                request.title,
                request.description,
                request.domain,
                request.intent,
                " ".join(request.tags),
                " ".join(request.use_cases),
                " ".join(request.triggers),
                request.content[:500],
            ]
        )

    @staticmethod
    def _warnings(request: AddPromptRequest) -> list[str]:
        warnings: list[str] = []
        warnings.extend(str(item) for item in request.quality.get("source_warnings") or [])
        content = request.content.strip()
        if len(content) < 80:
            warnings.append("short_content")
        if _looks_like_article_or_note(content):
            warnings.append("looks_like_article_or_note")
        if not request.description.strip():
            warnings.append("missing_description")
        if not request.outputs:
            warnings.append("missing_outputs")
        return warnings

    def _write(self, proposal: PromptProposal) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        proposal.path.write_text(
            json.dumps(proposal_dict(proposal), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _read(self, proposal_id: str) -> PromptProposal:
        path = self.root / f"{normalize_slug(proposal_id)}.json"
        if not path.is_file():
            raise FileNotFoundError(f"Prompt proposal not found: {proposal_id}")
        item = json.loads(path.read_text(encoding="utf-8"))
        request = _request_from_dict(item["request"])
        return PromptProposal(
            id=str(item["id"]),
            status=str(item.get("status") or "proposed"),
            action=str(item["action"]),
            title=str(item["title"]),
            request=request,
            similar=list(item.get("similar") or []),
            warnings=list(item.get("warnings") or []),
            rationale=list(item.get("rationale") or []),
            evaluation=dict(item.get("evaluation") or {}),
            path=path,
        )

    @staticmethod
    def _proposal_id(request: AddPromptRequest) -> str:
        stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        return normalize_slug(f"{stamp}-{request.title}")[:90]

    @staticmethod
    def _clean_title(title: str, content: str) -> str:
        clean = " ".join(str(title or "").split())
        if clean:
            return clean[:120]
        first = next((line.strip("# -*\t ") for line in content.splitlines() if line.strip()), "")
        return (first or "Untitled Prompt")[:120]

    @staticmethod
    def _clean_content(content: str) -> str:
        lines = [line.rstrip() for line in str(content or "").strip().splitlines()]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        return "\n".join(lines).strip()

    @staticmethod
    def _infer_kind(title: str, content: str) -> str:
        text = f"{title} {content}".casefold()
        if any(token in text for token in ["style", "风格", "interaction profile"]):
            return "source_note"
        if any(token in text for token in ["modifier", "suffix", "prefix", "修饰语", "附加"]):
            return "modifier"
        if any(token in text for token in ["review", "audit", "eval", "评估", "审查"]):
            return "eval_prompt"
        if any(token in text for token in ["workflow", "playbook", "skill", "流程", "工作流"]):
            return "playbook"
        return "full_prompt"

    @staticmethod
    def _infer_domain(title: str, content: str) -> str:
        text = f"{title} {content}".casefold()
        if any(token in text for token in ["prompt", "提示词"]):
            return "prompt-engineering"
        if any(token in text for token in ["dashboard", "ux", "ui", "页面", "体验"]):
            return "ux-review"
        if any(token in text for token in ["test", "smoke", "eval", "验证", "测试"]):
            return "testing"
        if any(token in text for token in ["skill", "agent", "codex", "claude"]):
            return "agent-automation"
        return "ai-coding"

    @staticmethod
    def _infer_intent(title: str, content: str, kind: str) -> str:
        text = f"{title} {content}".casefold()
        if "review" in text or "审查" in text:
            return "review"
        if "debug" in text or "排错" in text:
            return "debugging"
        if "refactor" in text or "重构" in text:
            return "refactoring"
        if "curat" in text or "整理" in text or "萃取" in text:
            return "curation"
        if kind == "eval_prompt":
            return "audit"
        if kind == "modifier":
            return "execute"
        return "execute"

    @staticmethod
    def _suggested_tags(domain: str, intent: str, kind: str) -> list[str]:
        return [item for item in [domain, intent, kind.replace("_", "-")] if item]

    @staticmethod
    def _use_case(title: str, domain: str, intent: str) -> str:
        if domain or intent:
            return f"{title} for {domain or 'general'} {intent or 'work'}".strip()
        return f"Reuse {title} for similar tasks"

    @staticmethod
    def _outputs(kind: str, intent: str) -> list[str]:
        if kind == "eval_prompt" or intent in {"audit", "review"}:
            return ["findings", "risks", "verification notes"]
        if kind == "playbook":
            return ["workflow steps", "checks", "handoff notes"]
        if kind == "source_note":
            return ["source reference", "curation decision"]
        if kind == "modifier":
            return ["adjusted instructions"]
        return ["actionable response", "verification result"]

    @staticmethod
    def _description(title: str, kind: str, domain: str, intent: str) -> str:
        return f"Reusable {kind.replace('_', ' ')} for {domain or 'general'} {intent or 'work'}: {title}."

    @staticmethod
    def _triggers(title: str, content: str) -> list[str]:
        tokens = [token for token in _tokens(f"{title} {content}") if len(token) >= 3]
        return tokens[:5] or [title]

    @staticmethod
    def _quality_score(
        content: str,
        description: str,
        use_cases: list[str],
        outputs: list[str],
    ) -> float:
        return proposal_quality_score(content, description, use_cases, outputs)

    @staticmethod
    def _professional_content(
        *,
        title: str,
        content: str,
        kind: str,
        domain: str,
        intent: str,
        use_cases: list[str],
        triggers: list[str],
        inputs: list[str],
        outputs: list[str],
        commitments: set[str],
    ) -> str:
        if _looks_structured(content):
            return content
        return _copy_ready_prompt(
            title=title,
            content=content,
            kind=kind,
            intent=intent,
            commitments=commitments,
            outputs=outputs,
        )


def _use_line(title: str, kind: str, domain: str, intent: str) -> str:
    if kind == "eval_prompt" or intent in {"audit", "review"}:
        return f"审查 {title}，只报告有证据的问题。"
    if kind == "playbook":
        return f"把 {title} 相关工作整理成可复用流程。"
    if kind in {"style_profile", "modifier"}:
        return "在匹配场景下调整 agent 行为，不覆盖用户目标。"
    return f"处理 {domain or 'general'} / {intent or 'execute'} 场景里的 {title}。"


def _copy_ready_prompt(
    *,
    title: str,
    content: str,
    kind: str,
    intent: str,
    commitments: set[str],
    outputs: list[str],
) -> str:
    source = _source_focus(content)
    if kind == "eval_prompt" or intent in {"audit", "review"}:
        prompt = (
            f"Review the current change for {title.lower()}.\n\n"
            "Inspect the relevant diff, files, tests, data, screenshots, logs, and recent "
            "failures before judging risk. Identify the change boundary first: user request, "
            "base commit, diff range, PR, touched files, changed data, or affected prompt."
        )
        if source:
            prompt += f" Focus on this requirement: {source}"
        if commitments:
            prompt += _commitment_guidance(commitments)
        prompt += (
            "\n\nStart with deterministic verification. Add focused AI eval only when the "
            "change needs qualitative judgment, such as prompt behavior, summarization "
            "quality, dashboard usefulness, agent routing, or knowledge retrieval quality."
            "\n\nReturn:"
        )
        output_keys = _copy_ready_output_keys(outputs) or [
            "findings",
            "risks",
            "verification_notes",
        ]
        prompt += "".join(f"\n- {key}: {_output_description(key)}" for key in output_keys)
        prompt += (
            "\n\nDo not claim unrun checks passed. Do not use AI eval as a substitute for "
            "deterministic tests. Do not skip checks directly related to the changed risk "
            "area just to save time."
        )
        return prompt
    if kind == "playbook":
        prompt = (
            f"Turn the current {title} task into an executable workflow.\n\n"
            "Identify the goal, inputs, outputs, constraints, and success criteria. "
            "Break the work into ordered steps, include verification for each risky step, "
            "and call out failure handling."
        )
        if source:
            prompt += f"\n\nPreserve this reusable requirement: {source}"
        if commitments:
            prompt += _commitment_guidance(commitments)
        prompt += "\n\nReturn workflow steps, checks, and handoff notes."
        return prompt
    prompt = (
        f"Handle the current {title} task.\n\n"
        "Clarify the goal from the available context, apply the relevant constraints, "
        "execute the smallest useful plan, and report the result with evidence."
    )
    if source:
        prompt += f"\n\nUse this reusable requirement: {source}"
    if commitments:
        prompt += _commitment_guidance(commitments)
    prompt += "\n\nReturn the result, supporting evidence, and remaining risks."
    return prompt


def _semantic_commitments(title: str, content: str) -> set[str]:
    text = f"{title}\n{content}".casefold()
    commitments: set[str] = set()
    if any(token in text for token in ["verify", "verification", "验证", "校验", "交付"]):
        commitments.add("verification")
    if any(token in text for token in ["rerun", "re-run", "复跑", "重跑", "再次运行"]):
        commitments.add("rerun")
    if any(
        token in text
        for token in [
            "harden",
            "hardening",
            "solidify",
            "codify",
            "persist",
            "preserve",
            "固化",
            "沉淀",
            "长期",
            "后续",
        ]
    ):
        commitments.add("hardening")
    return commitments


def _augment_outputs(outputs: list[str], commitments: set[str]) -> list[str]:
    extra: list[str] = []
    if "verification" in commitments:
        extra.extend(["verification_plan", "evidence"])
    if "rerun" in commitments:
        extra.extend(["rerun_instructions"])
    if "hardening" in commitments:
        extra.extend(["hardened_assets"])
    return _unique([*outputs, *extra])


def _commitment_guidance(commitments: set[str]) -> str:
    lines: list[str] = []
    if "verification" in commitments:
        lines.append(
            "Tie every recommendation to concrete verification evidence: commands run, "
            "tests, screenshots, logs, data checks, or explicit gaps."
        )
    if "rerun" in commitments:
        lines.append(
            "Make the result rerunnable: name the exact command, test, smoke script, AI eval "
            "suite, fixture, or manual checklist needed to repeat the check later."
        )
    if "hardening" in commitments:
        lines.append(
            "Do not stop at reporting. Convert useful discoveries into hardened assets such "
            "as regression tests, smoke checks, AI eval cases, prompts, docs, scripts, or "
            "follow-up tasks. Explain what was added and what still needs to be codified."
        )
    if not lines:
        return ""
    return "\n\n" + " ".join(lines)


def _copy_ready_output_keys(outputs: list[str]) -> list[str]:
    keys: list[str] = []
    for output in outputs:
        key = (
            str(output or "")
            .strip()
            .replace(" ", "_")
            .replace("-", "_")
            .replace("：", "")
            .replace(":", "")
            .casefold()
        )
        if key and key not in keys:
            keys.append(key)
    return keys


def _output_description(key: str) -> str:
    descriptions = {
        "selected_suites": "checks or AI eval suites to run",
        "commands": "exact commands to execute",
        "rationale": "why each selected check is needed",
        "skipped_checks": "checks intentionally skipped and why",
        "skipped": "checks intentionally skipped and why",
        "verification_plan": "focused checks to run before delivery",
        "evidence": "commands, pass/fail status, artifacts, screenshots, logs, or observed results",
        "hardened_assets": "tests, smoke checks, AI eval cases, docs, prompts, scripts, or tasks added for future reuse",
        "rerun_instructions": "exact steps or commands to repeat the verification later",
        "escalation_conditions": "conditions that require broader or full eval",
        "escalation": "conditions that require broader or full eval",
        "findings": "evidence-backed issues, ordered by severity",
        "risks": "residual risks and untested areas",
        "verification_notes": "commands, artifacts, or observations used as evidence",
    }
    return descriptions.get(key, key.replace("_", " "))


def _merge_prompt_request(
    existing: Prompt,
    incoming: AddPromptRequest,
    *,
    target_title: str,
) -> AddPromptRequest:
    return AddPromptRequest(
        title=target_title,
        content=_merge_prompt_content(existing.content, incoming.content),
        description=incoming.description or existing.description,
        tags=_unique([*existing.tags, *incoming.tags]),
        use_cases=_unique([*existing.use_cases, *incoming.use_cases]),
        source_refs=_unique([*existing.source_refs, *incoming.source_refs]),
        kind=incoming.kind or existing.kind,
        domain=incoming.domain or existing.domain,
        intent=incoming.intent or existing.intent,
        surfaces=_unique([*existing.surfaces, *incoming.surfaces]),
        triggers=_unique([*existing.triggers, *incoming.triggers]),
        inputs=_unique([*existing.inputs, *incoming.inputs]),
        outputs=_unique([*existing.outputs, *incoming.outputs]),
        quality={
            **existing.quality,
            **incoming.quality,
            "status": incoming.quality.get("status")
            or existing.quality.get("status")
            or "proposed",
            "score": max(
                float(existing.quality.get("score") or 0),
                float(incoming.quality.get("score") or 0),
            ),
        },
    )


def _merge_prompt_content(existing: str, incoming: str) -> str:
    left = str(existing or "").strip()
    right = str(incoming or "").strip()
    if not left:
        return right
    if not right:
        return left
    if _fingerprint(left) == _fingerprint(right) or right in left:
        return left
    if left in right:
        return right
    return f"{left}\n\nAdditional guidance:\n{right}"


def _concise_rules(kind: str, intent: str, source: str) -> list[str]:
    if kind == "eval_prompt" or intent in {"audit", "review"}:
        return [
            "先读相关上下文、代码、数据或截图，再判断。",
            "每条 finding 都给证据、影响和最小修法。",
            "按严重度排序；没有实质问题就明确说没有。",
        ]
    if kind == "playbook":
        return [
            "先确认目标、输入、输出和成功标准。",
            "把流程拆成可执行步骤，并标出失败时怎么处理。",
            "能验证的地方给出命令、数据或页面状态。",
        ]
    if kind in {"style_profile", "modifier"}:
        return [
            "只在触发条件匹配时应用。",
            "把短指令或修饰语转换成具体行为。",
            "保持输出简短，不展开无关解释。",
        ]
    rules = [
        "先理解目标和约束。",
        "按最小可行步骤执行。",
        "输出结果、依据和必要风险。",
    ]
    if source:
        rules.append("提炼可复用行为，去掉一次性噪音。")
    return rules


def _concise_boundaries(kind: str, intent: str) -> list[str]:
    boundaries = [
        "不要编造事实、命令结果或验证结果。",
        "不要保留 token、webhook、个人路径等私密信息。",
    ]
    if kind == "eval_prompt" or intent in {"audit", "review"}:
        boundaries.append("不要把低置信度风格意见当成缺陷。")
    if kind in {"style_profile", "modifier"}:
        boundaries.append("不要覆盖更高优先级的用户、系统或安全指令。")
    return boundaries


def _source_focus(content: str) -> str:
    source = " ".join(str(content or "").split())
    if not source:
        return ""
    if _looks_like_metadata_card(source):
        return ""
    if _looks_like_historical_interaction_rule(source) or _looks_like_chat_fragment(source):
        return ""
    if len(source) > 260:
        return source[:257].rstrip() + "..."
    return source


def proposal_dict(proposal: PromptProposal) -> dict[str, Any]:
    return {
        "id": proposal.id,
        "status": proposal.status,
        "action": proposal.action,
        "title": proposal.title,
        "path": compact_user_path(proposal.path),
        "request": request_dict(proposal.request),
        "similar": proposal.similar,
        "warnings": proposal.warnings,
        "rationale": proposal.rationale,
        "evaluation": proposal.evaluation,
        "next_steps": _next_steps(proposal),
    }


def request_dict(request: AddPromptRequest) -> dict[str, Any]:
    return {
        "title": request.title,
        "content": request.content,
        "description": request.description,
        "tags": request.tags,
        "use_cases": request.use_cases,
        "source_refs": request.source_refs,
        "kind": request.kind,
        "domain": request.domain,
        "intent": request.intent,
        "surfaces": request.surfaces,
        "triggers": request.triggers,
        "inputs": request.inputs,
        "outputs": request.outputs,
        "quality": request.quality,
    }


def _request_from_dict(item: dict[str, Any]) -> AddPromptRequest:
    quality = item.get("quality")
    return AddPromptRequest(
        title=str(item.get("title") or ""),
        content=str(item.get("content") or ""),
        description=str(item.get("description") or ""),
        tags=_as_list(item.get("tags")),
        use_cases=_as_list(item.get("use_cases")),
        source_refs=_as_list(item.get("source_refs")),
        kind=str(item.get("kind") or "full_prompt"),
        domain=str(item.get("domain") or ""),
        intent=str(item.get("intent") or ""),
        surfaces=_as_list(item.get("surfaces")),
        triggers=_as_list(item.get("triggers")),
        inputs=_as_list(item.get("inputs")),
        outputs=_as_list(item.get("outputs")),
        quality=quality if isinstance(quality, dict) else {},
    )


def _next_steps(proposal: PromptProposal) -> list[str]:
    steps = [
        f"Review proposal: alcove prompt proposal {proposal.id} --json",
    ]
    if proposal.action in {"create_new", "create_new_after_review", "update_existing"}:
        steps.append(f"Save optimized prompt: alcove prompt save --proposal-id {proposal.id}")
    elif proposal.action == "merge_into_existing":
        steps.append(
            "Inspect the similar prompts and update/archive manually if the overlap is real."
        )
    elif proposal.action == "save_as_knowledge_note_not_prompt":
        steps.append("Save this as a managed KB note/source instead of a reusable prompt.")
    else:
        steps.append("Do not save unless the user explicitly confirms it should be reusable.")
    return steps


def _looks_structured(content: str) -> bool:
    text = str(content or "").casefold()
    copy_ready_signals = [
        "return",
        "respond with",
        "review",
        "inspect",
        "rewrite",
        "extract",
        "analyze",
        "输出",
        "返回",
        "审查",
        "检查",
        "改写",
        "提取",
        "分析",
    ]
    if (
        _looks_like_metadata_card(text)
        and sum(1 for signal in copy_ready_signals if signal in text) < 3
    ):
        return False
    old_boilerplate = [
        "role and purpose",
        "required inputs",
        "operating rules",
        "output contract",
        "guardrails and stop conditions",
        "source material to preserve",
    ]
    if sum(1 for signal in old_boilerplate if signal in text) >= 3:
        return False
    signals = [
        "用于",
        "use when",
        "触发",
        "做法",
        "输出",
        "边界",
        "验证",
        "不要",
        "检查",
        "report",
        "output",
    ]
    return sum(1 for signal in signals if signal in text) >= 3


def _bullets(values: list[str]) -> list[str]:
    return [f"- {value}" for value in _unique(values) if value]


def _numbered(values: list[str]) -> list[str]:
    return [f"{index}. {value}" for index, value in enumerate(values, 1)]


def _as_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = str(value or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
    return result


def _clean_source_refs(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        ref = str(value or "").strip()
        if not ref:
            continue
        lower = ref.casefold()
        normalized = lower.replace("_", "-").replace(" ", "-")
        if "prompt-guidelines" in normalized:
            cleaned.append("source:prompt-guidelines")
        elif "prompt" in normalized and ("archive" in normalized or "collection" in normalized):
            cleaned.append("source:historical-prompt-archive")
        elif "ai" in normalized and "input" in normalized:
            cleaned.append("source:historical-ai-input-archive")
        elif lower.startswith("~/programming/") or lower.startswith(str(Path.home()).casefold()):
            cleaned.append("source:local-user-archive")
        else:
            cleaned.append(ref)
    return _unique(cleaned)


def _tokens(value: str) -> list[str]:
    return ordered_prompt_tokens(value)


def _fingerprint(content: str) -> str:
    return prompt_similarity_fingerprint(content)


def _source_warnings(content: str) -> list[str]:
    warnings: list[str] = []
    text = str(content or "").strip()
    if len(text) < 80:
        warnings.append("source_too_short")
    if _looks_like_historical_interaction_rule(text):
        warnings.append("looks_like_historical_interaction_rule")
    elif _looks_like_chat_fragment(text):
        warnings.append("looks_like_chat_fragment")
    return warnings


def _looks_like_metadata_card(content: str) -> bool:
    text = str(content or "").casefold()
    metadata_card_signals = [
        "用于",
        "触发",
        "输出",
        "边界",
        "use case",
        "trigger",
        "tags",
        "surfaces",
    ]
    return sum(1 for signal in metadata_card_signals if signal in text) >= 3


def _looks_like_historical_interaction_rule(content: str) -> bool:
    text = str(content or "")
    lower = text.casefold()
    historical_markers = [
        "我经常用",
        "短指令",
        "一两个字",
        "用户用短句",
        "历史 ai",
        "chat transcript",
    ]
    command_markers = ["继续", "做完了吗", "提交吧", "推送吧", "方案 b", "那就 1"]
    return (
        any(marker in lower for marker in historical_markers)
        and sum(1 for marker in command_markers if marker.casefold() in lower) >= 2
    )


def _looks_like_chat_fragment(content: str) -> bool:
    lower = str(content or "").casefold()
    weak_patterns = [
        "继续就继续",
        "提交就提交",
        "别解释",
        "不要重新解释",
        "一句话说",
    ]
    action_prompt_signals = [
        "review",
        "check",
        "verify",
        "rewrite",
        "extract",
        "design",
        "return",
        "output",
        "审查",
        "检查",
        "验证",
        "整理",
        "输出",
    ]
    return any(pattern in lower for pattern in weak_patterns) and not any(
        signal in lower for signal in action_prompt_signals
    )


def _looks_like_article_or_note(content: str) -> bool:
    lower = content.casefold()
    if any(marker in lower for marker in ["http://", "https://", "摘要", "原文", "article"]):
        imperative = any(
            marker in lower
            for marker in ["you are", "你的任务", "请", "review", "analyze", "output", "return"]
        )
        return not imperative
    return False
