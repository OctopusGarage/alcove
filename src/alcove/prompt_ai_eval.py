from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


PROMPT_LIBRARY_EVAL_PROMPT = """# Prompt Library Quality Reviewer

Evaluate one reusable prompt-library candidate. The candidate is already parsed
into metadata and body fields. Judge the prompt as an instruction another agent
could copy and use directly.

Run two review rounds:

1. Professional quality review
   - Is the prompt body copy-ready, direct, and free of library metadata cards?
   - Are the goal, action order, output contract, and boundaries clear?
   - Is the wording concise without generic template padding?
   - Would a capable agent know what evidence to inspect and what to return?

2. Adversarial reuse review
   - Does the prompt satisfy every semantic promise in its title and description?
   - Would it still work outside the original chat or local project?
   - Does it avoid private paths, stale project names, and one-off context?
   - If it says verify, rerun, harden, codify, or preserve, does it require
     concrete evidence and reusable follow-up artifacts?

Return JSON only:
{
  "verdict": "pass | needs_revision",
  "score": 0,
  "rounds": [
    {
      "name": "professional_quality",
      "score": 0,
      "findings": [],
      "required_fixes": []
    },
    {
      "name": "adversarial_reuse",
      "score": 0,
      "findings": [],
      "required_fixes": []
    }
  ],
  "must_fix": [],
  "suggestions": []
}
"""


def evaluate_prompt_candidate(prompt: Any) -> dict[str, Any]:
    """Run deterministic guardrails that mirror the AI reviewer rubric.

    The prompt text above is the reviewer contract for Codex/Claude-backed eval.
    These checks keep proposal/save behavior deterministic in tests and CI while
    preserving the same quality dimensions for a real AI reviewer.
    """

    professional = _professional_quality_round(prompt)
    adversarial = _adversarial_reuse_round(prompt)
    rounds = [professional, adversarial]
    must_fix = [
        issue for round_result in rounds for issue in round_result["required_fixes"] if issue
    ]
    score = round(sum(float(item["score"]) for item in rounds) / len(rounds), 2)
    verdict = "pass" if score >= 0.8 and not must_fix else "needs_revision"
    return {
        "verdict": verdict,
        "score": score,
        "rounds": rounds,
        "must_fix": must_fix,
        "suggestions": _suggestions(prompt, must_fix),
        "reviewer_prompt": PROMPT_LIBRARY_EVAL_PROMPT,
    }


def configured_prompt_ai_eval_provider(config: dict[str, Any] | None = None) -> str:
    explicit = os.environ.get("ALCOVE_PROMPT_AI_EVAL_PROVIDER", "").strip().casefold()
    if explicit:
        return explicit
    data = config or {}
    prompt_config = data.get("prompt_library")
    if isinstance(prompt_config, dict):
        provider = str(prompt_config.get("ai_eval_provider") or "").strip().casefold()
        if provider:
            return provider
    prompts_config = data.get("prompts")
    if isinstance(prompts_config, dict):
        provider = str(prompts_config.get("ai_eval_provider") or "").strip().casefold()
        if provider:
            return provider
    return "none"


def run_external_prompt_ai_eval(
    prompt: Any,
    *,
    provider: str,
    cwd: Path,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    normalized = str(provider or "none").strip().casefold()
    if normalized in {"", "none", "off", "false", "0"}:
        return {"status": "skipped", "provider": "none"}
    if normalized not in {"codex", "claude"}:
        return {
            "status": "error",
            "provider": normalized,
            "message": "unsupported prompt AI eval provider",
        }
    binary = shutil.which(normalized)
    if not binary:
        return {
            "status": "error",
            "provider": normalized,
            "message": f"{normalized} command not found",
        }
    review_prompt = build_external_prompt_ai_eval_prompt(prompt)
    try:
        if normalized == "codex":
            with tempfile.TemporaryDirectory(prefix="alcove-prompt-eval-") as temp:
                output_path = Path(temp) / "review.txt"
                subprocess.run(  # noqa: S603 - provider is restricted to codex/claude binaries.
                    [
                        binary,
                        "exec",
                        "--cd",
                        str(cwd),
                        "--sandbox",
                        "read-only",
                        "--output-last-message",
                        str(output_path),
                        "-",
                    ],
                    input=review_prompt,
                    text=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    timeout=timeout_seconds,
                    check=False,
                )
                raw = output_path.read_text(encoding="utf-8") if output_path.is_file() else ""
        else:
            completed = subprocess.run(  # noqa: S603 - provider is restricted to codex/claude binaries.
                [binary, "-p", "--permission-mode", "dontAsk", "--allowedTools", "Read"],
                input=review_prompt,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds,
                check=False,
            )
            raw = completed.stdout
        payload = _parse_review_json(raw)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "status": "error",
            "provider": normalized,
            "message": str(exc),
        }
    if not payload:
        return {
            "status": "error",
            "provider": normalized,
            "message": "AI eval did not return parseable JSON",
        }
    return {"status": "completed", "provider": normalized, "review": payload}


def build_external_prompt_ai_eval_prompt(prompt: Any) -> str:
    return f"""{PROMPT_LIBRARY_EVAL_PROMPT}

Candidate:

```json
{json.dumps(_prompt_candidate_payload(prompt), ensure_ascii=False, indent=2)}
```

Return JSON only. Do not edit files.
"""


def _professional_quality_round(prompt: Any) -> dict[str, Any]:
    content = _field(prompt, "content")
    text = f"{_field(prompt, 'title')}\n{_field(prompt, 'description')}\n{content}".casefold()
    findings: list[str] = []
    fixes: list[str] = []
    score = 1.0
    metadata_markers = ["用于：", "触发：", "输出：", "边界：", "use case:", "tags:"]
    if any(marker.casefold() in content.casefold() for marker in metadata_markers):
        score -= 0.25
        fixes.append("Remove library metadata-card headings from the prompt body.")
    if "return:" not in text and "输出" not in text and "返回" not in text:
        score -= 0.2
        fixes.append("Add an explicit output contract.")
    if not any(token in text for token in ["evidence", "证据", "verify", "验证", "检查"]):
        score -= 0.15
        findings.append("Evidence or inspection requirements are weak.")
    if len(content.strip()) < 160:
        score -= 0.15
        findings.append("Prompt body may be too short to guide reliable reuse.")
    if any(
        token in text
        for token in ["role and purpose", "required inputs", "source material to preserve"]
    ):
        score -= 0.2
        fixes.append("Remove generic prompt-template boilerplate.")
    return _round("professional_quality", score, findings, fixes)


def _adversarial_reuse_round(prompt: Any) -> dict[str, Any]:
    title = _field(prompt, "title")
    content = _field(prompt, "content")
    body_text = f"{_field(prompt, 'description')}\n{content}".casefold()
    findings: list[str] = []
    fixes: list[str] = []
    score = 1.0
    for name, title_tokens, required_tokens, fix in [
        (
            "verification",
            ("verify", "verification", "验证", "校验", "交付"),
            ("evidence", "verify", "verification", "checked", "验证", "证据"),
            "The title promises verification; require concrete evidence and checked artifacts.",
        ),
        (
            "rerun",
            ("rerun", "re-run", "复跑", "重跑", "再次运行"),
            ("rerun", "repeat", "command", "commands", "复跑", "重跑", "命令"),
            "The title promises rerun; require exact commands or repeatable steps.",
        ),
        (
            "hardening",
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
            "The title promises hardening; require reusable artifacts such as tests, evals, docs, scripts, or tasks.",
        ),
    ]:
        if any(token in title.casefold() for token in title_tokens) and not any(
            token in body_text for token in required_tokens
        ):
            score -= 0.24
            fixes.append(fix)
            findings.append(f"Missing title commitment: {name}.")
    if any(token in f"{title}\n{body_text}" for token in ["/users/", "ys/悦数"]):
        score -= 0.3
        fixes.append("Remove private local paths or personal organization names.")
    return _round("adversarial_reuse", score, findings, fixes)


def _round(name: str, score: float, findings: list[str], fixes: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "score": round(max(0.0, min(1.0, score)), 2),
        "findings": findings,
        "required_fixes": fixes,
    }


def _suggestions(prompt: Any, must_fix: list[str]) -> list[str]:
    if must_fix:
        return ["Revise the prompt body, then rerun prompt proposal/eval before saving."]
    if _field(prompt, "kind") == "eval_prompt":
        return ["Keep deterministic checks separate from qualitative AI eval in the prompt."]
    return []


def _field(prompt: Any, name: str) -> str:
    return str(getattr(prompt, name, "") or "")


def _prompt_candidate_payload(prompt: Any) -> dict[str, Any]:
    return {
        "title": _field(prompt, "title"),
        "description": _field(prompt, "description"),
        "kind": _field(prompt, "kind"),
        "domain": _field(prompt, "domain"),
        "intent": _field(prompt, "intent"),
        "tags": list(getattr(prompt, "tags", []) or []),
        "use_cases": list(getattr(prompt, "use_cases", []) or []),
        "triggers": list(getattr(prompt, "triggers", []) or []),
        "outputs": list(getattr(prompt, "outputs", []) or []),
        "content": _field(prompt, "content"),
    }


def _parse_review_json(raw: str) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\\s*", "", text)
        text = re.sub(r"\\s*```$", "", text).strip()
    candidates = [text]
    match = re.search(r"\\{.*\\}", text, flags=re.S)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None
