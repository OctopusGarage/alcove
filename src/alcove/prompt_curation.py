from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from alcove.home import AlcoveHome
from alcove.markdown import normalize_slug
from alcove.paths import compact_user_path
from alcove.prompts import AddPromptRequest, PromptResult, PromptsModule
from alcove.runtime import AlcoveRuntime
from alcove.workspace import Workspace


CANDIDATE_INDEX_SCHEMA = "alcove/prompt-candidates-index/v1"
HEADING_RE = re.compile(r"^(#{1,4})\s+(.+?)\s*$", re.MULTILINE)
FENCE_RE = re.compile(r"```(?:[a-zA-Z0-9_-]+)?\n(.*?)```", re.DOTALL)


@dataclass(frozen=True)
class PromptCandidate:
    id: str
    title: str
    content: str
    description: str
    kind: str
    domain: str
    intent: str
    tags: list[str]
    use_cases: list[str]
    triggers: list[str]
    inputs: list[str]
    outputs: list[str]
    source_refs: list[str]
    score: float
    reasons: list[str]


class PromptCurationModule:
    def __init__(self, workspace: Workspace | None = None, home: AlcoveHome | None = None) -> None:
        self.runtime = AlcoveRuntime.from_modules(workspace=workspace, home=home)
        self.prompts = PromptsModule(workspace=workspace, home=home)
        self.candidates_root = self.runtime.prompts_root / "candidates"
        self.index_path = self.candidates_root / "index.json"

    def scan(self, source_paths: list[Path]) -> dict[str, Any]:
        candidates: list[PromptCandidate] = []
        for source_path in source_paths:
            candidates.extend(self._scan_path(Path(source_path).expanduser()))
        deduped = self._dedupe(candidates)
        self.candidates_root.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": CANDIDATE_INDEX_SCHEMA,
            "count": len(deduped),
            "candidates": [candidate_dict(candidate) for candidate in deduped],
        }
        self.index_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return {"index_path": compact_user_path(self.index_path), "count": len(deduped)}

    def list_candidates(self, min_score: float = 0.0) -> list[PromptCandidate]:
        if not self.index_path.is_file():
            return []
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        raw_items = payload.get("candidates") if isinstance(payload, dict) else []
        items = raw_items if isinstance(raw_items, list) else []
        candidates = [candidate_from_dict(item) for item in items if isinstance(item, dict)]
        return [candidate for candidate in candidates if candidate.score >= min_score]

    def promote(self, min_score: float = 0.72, limit: int = 0) -> dict[str, Any]:
        candidates = sorted(
            self.list_candidates(min_score=min_score),
            key=lambda candidate: (-candidate.score, candidate.title),
        )
        if limit > 0:
            candidates = candidates[:limit]
        results: list[PromptResult] = []
        for candidate in candidates:
            results.append(self.prompts.save(_request_from_candidate(candidate)))
        return {
            "status": "promoted",
            "count": len(results),
            "prompts": [
                {
                    "id": result.prompt.id,
                    "title": result.prompt.title,
                    "path": f"prompts/{result.path.name}",
                }
                for result in results
            ],
            "index_path": compact_user_path(self.prompts.index_path),
        }

    def _scan_path(self, source_path: Path) -> list[PromptCandidate]:
        if not source_path.exists():
            return []
        if source_path.is_file():
            return self._scan_file(source_path)
        candidates: list[PromptCandidate] = []
        for path in sorted(source_path.rglob("*"), key=lambda item: item.as_posix()):
            if not path.is_file() or _ignored_path(path):
                continue
            if path.suffix.lower() not in {".md", ".txt"}:
                continue
            candidates.extend(self._scan_file(path))
        return candidates

    def _scan_file(self, path: Path) -> list[PromptCandidate]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not text.strip():
            return []
        if path.name == "style_prompts.md":
            return self._scan_style_prompts(path, text)
        if "可粘贴 prompt 片段" in text:
            return self._scan_style_prompts(path, text)
        return self._scan_markdown_like(path, text)

    def _scan_style_prompts(self, path: Path, text: str) -> list[PromptCandidate]:
        candidates: list[PromptCandidate] = []
        sections = _heading_sections(text, level=2)
        for heading, body in sections:
            if "可粘贴 prompt 片段" not in body:
                continue
            fences = FENCE_RE.findall(body)
            if not fences:
                continue
            content = max((fence.strip() for fence in fences), key=len)
            intent = _intent_from_heading(heading)
            title = f"用户交互风格：{heading.strip()}"
            candidates.append(
                self._candidate(
                    title=title,
                    content=content,
                    description=f"{heading.strip()} 场景下可复用的 agent 行为规则候选。",
                    kind="source_note",
                    domain="ai-coding",
                    intent=intent,
                    tags=["ai-coding", "style-profile", intent],
                    use_cases=[f"{heading.strip()} 场景下指导 AI agent 正确响应用户意图"],
                    triggers=_trigger_words(content, heading),
                    inputs=["用户当前消息", "当前项目上下文"],
                    outputs=["source reference", "curation decision"],
                    source=path,
                    raw_score=0.58,
                    reasons=["agent behavior note, not an active prompt"],
                )
            )
        return candidates

    def _scan_markdown_like(self, path: Path, text: str) -> list[PromptCandidate]:
        candidates: list[PromptCandidate] = []
        sections = _heading_sections(text, level=1) or [(path.stem, text)]
        for heading, body in sections:
            content = _best_prompt_content(body)
            if not content:
                continue
            title = _candidate_title(path, heading)
            kind = _infer_kind(title, content)
            domain = _infer_domain(title, content, path)
            score, reasons = _quality_score(title, content, path)
            if score < 0.52:
                continue
            candidates.append(
                self._candidate(
                    title=title,
                    content=content,
                    description=_description_from_content(title, content),
                    kind=kind,
                    domain=domain,
                    intent=_infer_intent(title, content),
                    tags=_tags_for(title, content, domain, kind),
                    use_cases=_use_cases_for(title, content, domain, kind),
                    triggers=_trigger_words(content, title),
                    inputs=_inputs_for(content),
                    outputs=_outputs_for(content),
                    source=path,
                    raw_score=score,
                    reasons=reasons,
                )
            )
        return candidates

    def _candidate(
        self,
        *,
        title: str,
        content: str,
        description: str,
        kind: str,
        domain: str,
        intent: str,
        tags: list[str],
        use_cases: list[str],
        triggers: list[str],
        inputs: list[str],
        outputs: list[str],
        source: Path,
        raw_score: float,
        reasons: list[str],
    ) -> PromptCandidate:
        source_ref = compact_user_path(source)
        candidate_id = normalize_slug(f"{title}-{source_ref}", max_len=120)
        return PromptCandidate(
            id=candidate_id,
            title=title.strip(),
            content=content.strip(),
            description=description.strip(),
            kind=kind,
            domain=domain,
            intent=intent,
            tags=_clean_list(tags),
            use_cases=_clean_list(use_cases),
            triggers=_clean_list(triggers)[:12],
            inputs=_clean_list(inputs),
            outputs=_clean_list(outputs),
            source_refs=[source_ref],
            score=round(max(0.0, min(1.0, raw_score)), 3),
            reasons=_clean_list(reasons),
        )

    def _dedupe(self, candidates: list[PromptCandidate]) -> list[PromptCandidate]:
        by_key: dict[str, PromptCandidate] = {}
        for candidate in candidates:
            key = normalize_slug(candidate.title)
            current = by_key.get(key)
            if current is None or candidate.score > current.score:
                by_key[key] = candidate
        return sorted(by_key.values(), key=lambda item: (-item.score, item.title))


def candidate_dict(candidate: PromptCandidate) -> dict[str, Any]:
    return {
        "id": candidate.id,
        "title": candidate.title,
        "content": candidate.content,
        "description": candidate.description,
        "kind": candidate.kind,
        "domain": candidate.domain,
        "intent": candidate.intent,
        "tags": candidate.tags,
        "use_cases": candidate.use_cases,
        "triggers": candidate.triggers,
        "inputs": candidate.inputs,
        "outputs": candidate.outputs,
        "source_refs": candidate.source_refs,
        "score": candidate.score,
        "reasons": candidate.reasons,
    }


def candidate_from_dict(item: dict[str, Any]) -> PromptCandidate:
    return PromptCandidate(
        id=str(item.get("id") or ""),
        title=str(item.get("title") or ""),
        content=str(item.get("content") or ""),
        description=str(item.get("description") or ""),
        kind=str(item.get("kind") or "full_prompt"),
        domain=str(item.get("domain") or ""),
        intent=str(item.get("intent") or ""),
        tags=_list(item.get("tags")),
        use_cases=_list(item.get("use_cases")),
        triggers=_list(item.get("triggers")),
        inputs=_list(item.get("inputs")),
        outputs=_list(item.get("outputs")),
        source_refs=_list(item.get("source_refs")),
        score=float(item.get("score") or 0.0),
        reasons=_list(item.get("reasons")),
    )


def _request_from_candidate(candidate: PromptCandidate) -> AddPromptRequest:
    return AddPromptRequest(
        title=candidate.title,
        content=candidate.content,
        description=candidate.description,
        tags=candidate.tags,
        use_cases=candidate.use_cases,
        source_refs=candidate.source_refs,
        kind=candidate.kind,
        domain=candidate.domain,
        intent=candidate.intent,
        surfaces=["codex", "claude-code", "generic-llm"],
        triggers=candidate.triggers,
        inputs=candidate.inputs,
        outputs=candidate.outputs,
        quality={
            "status": "curated",
            "score": candidate.score,
            "notes": "; ".join(candidate.reasons[:3]),
        },
    )


def _heading_sections(text: str, level: int) -> list[tuple[str, str]]:
    headings = [match for match in HEADING_RE.finditer(text) if len(match.group(1)) == level]
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(headings):
        start = match.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        sections.append((match.group(2).strip(), text[start:end].strip()))
    return sections


def _best_prompt_content(body: str) -> str:
    fences = [fence.strip() for fence in FENCE_RE.findall(body) if len(fence.strip()) > 80]
    if fences:
        return str(max(fences, key=len))
    markers = ["完整 Prompt", "Agent 探索式", "优化后的提示词", "Prompt：", "# 任务"]
    if any(marker in body for marker in markers) and len(body.strip()) > 120:
        return _trim_content(body.strip())
    return ""


def _trim_content(value: str, limit: int = 6000) -> str:
    value = value.strip()
    return (
        value if len(value) <= limit else value[:limit].rstrip() + "\n\n[...trimmed for reuse...]"
    )


def _candidate_title(path: Path, heading: str) -> str:
    cleaned = re.sub(r"^[\d.、\s-]+", "", heading).strip()
    if cleaned and cleaned.lower() not in {"prompt", "任务"}:
        return cleaned
    return path.stem.replace("_", " ").replace("-", " ").strip().title()


def _infer_kind(title: str, content: str) -> str:
    text = f"{title}\n{content}".casefold()
    if "style" in text or "风格" in text or "交互习惯" in text:
        return "source_note"
    if "eval" in text or "评估" in text or "验证" in text:
        return "eval_prompt"
    if "phase" in text or "step " in text or "阶段" in text or "workflow" in text:
        return "playbook"
    if len(content) < 500 and ("尾缀" in text or "片段" in text):
        return "fragment"
    return "full_prompt"


def _infer_domain(title: str, content: str, path: Path) -> str:
    text = f"{path.name}\n{title}\n{content}".casefold()
    checks = [
        (("review", "审查", "评审"), "review"),
        (("debug", "bug", "排错"), "debugging"),
        (("test", "eval", "验证", "测试"), "testing"),
        (("skill", "agent-browser", "browser", "spotify", "automation"), "agent-automation"),
        (("image", "midjourney", "dall", "生图", "配图"), "creative-media"),
        (("doc", "文档", "documentation"), "documentation"),
        (("coding", "code", "claude code", "codex"), "ai-coding"),
    ]
    for needles, domain in checks:
        if any(needle in text for needle in needles):
            return domain
    return "prompt-engineering"


def _infer_intent(title: str, content: str) -> str:
    text = f"{title}\n{content}".casefold()
    for intent in (
        "review",
        "debugging",
        "testing",
        "documentation",
        "refactoring",
        "config",
        "archive",
        "deploy",
        "coding",
        "planning",
    ):
        if intent in text:
            return intent
    if "审查" in text or "评审" in text:
        return "review"
    if "测试" in text or "验证" in text:
        return "testing"
    if "文档" in text:
        return "documentation"
    return ""


def _intent_from_heading(heading: str) -> str:
    value = heading.split("—", 1)[0].strip()
    value = re.sub(r"^\d+[.、]\s*", "", value)
    return normalize_slug(value)


def _quality_score(title: str, content: str, path: Path) -> tuple[float, list[str]]:
    score = 0.45
    reasons: list[str] = []
    if len(content) >= 240:
        score += 0.12
        reasons.append("substantial reusable content")
    if any(marker in content for marker in ("Output", "输出", "完成条件", "Rules", "约束")):
        score += 0.12
        reasons.append("has constraints or output format")
    if any(marker in content for marker in ("Step", "Phase", "阶段", "步骤")):
        score += 0.08
        reasons.append("has workflow structure")
    if any(marker in content for marker in ("不要", "Do NOT", "MUST", "严禁")):
        score += 0.08
        reasons.append("has explicit guardrails")
    if path.suffix.lower() == ".md":
        score += 0.04
        reasons.append("markdown source")
    if len(content) > 7000:
        score -= 0.08
        reasons.append("long source trimmed")
    return max(0.0, min(1.0, score)), reasons


def _description_from_content(title: str, content: str) -> str:
    first_line = next((line.strip() for line in content.splitlines() if line.strip()), "")
    if first_line and len(first_line) <= 140:
        return first_line
    return f"Reusable prompt curated from historical source for {title}."


def _tags_for(title: str, content: str, domain: str, kind: str) -> list[str]:
    tags = [domain, kind, "curated"]
    text = f"{title}\n{content}".casefold()
    for needle, tag in [
        ("codex", "codex"),
        ("claude", "claude-code"),
        ("review", "review"),
        ("debug", "debug"),
        ("test", "test"),
        ("eval", "ai-eval"),
        ("skill", "skill"),
        ("browser", "browser-automation"),
        ("文档", "docs"),
        ("审查", "review"),
    ]:
        if needle in text:
            tags.append(tag)
    return tags


def _use_cases_for(title: str, content: str, domain: str, kind: str) -> list[str]:
    use_case = {
        "source_note": "Keep source material for later prompt curation",
        "playbook": "Run a reusable multi-step workflow",
        "eval_prompt": "Evaluate quality and prevent prompt or workflow regression",
        "fragment": "Compose with a full prompt as an additional constraint",
    }.get(kind, "Reuse this prompt for a matching work scenario")
    return [use_case, f"{domain} scenario: {title}"]


def _trigger_words(content: str, title: str) -> list[str]:
    triggers = re.findall(r"\"([^\"]{2,30})\"", content)
    triggers.extend(re.findall(r"`([^`]{2,30})`", content))
    for word in re.split(r"[\s/|,，、]+", title):
        if 2 <= len(word) <= 30:
            triggers.append(word)
    return triggers


def _inputs_for(content: str) -> list[str]:
    text = content.casefold()
    if "file" in text or "文件" in text:
        return ["source files", "task context"]
    if "url" in text or "website" in text or "网页" in text:
        return ["target URL", "browser/session context"]
    return ["current user request", "available project context"]


def _outputs_for(content: str) -> list[str]:
    text = content.casefold()
    if "review" in text or "审查" in text:
        return ["findings", "recommended fixes"]
    if "skill" in text:
        return ["skill design", "workflow plan", "validation criteria"]
    if "image" in text or "生图" in text:
        return ["image prompt drafts"]
    return ["structured response matching the prompt contract"]


def _ignored_path(path: Path) -> bool:
    ignored_parts = {".git", "__pycache__", ".venv", "node_modules"}
    if any(part in ignored_parts for part in path.parts):
        return True
    raw_history_parts = {
        "user_inputs_by_source",
        "samples_by_intent",
        "intent_classification",
    }
    if "intent_classification" in path.parts and path.name != "style_prompts.md":
        return True
    if any(part in raw_history_parts for part in path.parts) and path.name != "style_prompts.md":
        return True
    return path.stat().st_size > 1_000_000


def _clean_list(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in out:
            out.append(item)
    return out


def _list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if value:
        return [str(value)]
    return []
