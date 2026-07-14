from __future__ import annotations

import hashlib
import re


TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
STOP_TOKENS = {
    "ai",
    "prompt",
    "prompts",
    "agent",
    "skill",
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "当前",
    "项目",
    "需要",
    "这个",
    "用户",
    "工作",
    "希望",
    "理解",
    "或者",
    "时候",
    "直接",
    "接着",
    "指令",
    "任务",
    "进行",
    "一下",
    "整理",
    "复用",
    "可复用",
    "成可复",
    "整理成",
    "内容",
    "输入",
    "清理",
    "重复",
}


def prompt_tokens(value: str, *, stop_tokens: set[str] | None = STOP_TOKENS) -> set[str]:
    tokens: set[str] = set()
    blocked = stop_tokens or set()
    for match in TOKEN_RE.finditer(str(value or "").casefold()):
        token = match.group(0)
        if len(token) < 2 or token in blocked:
            continue
        tokens.add(token)
        if CJK_RE.search(token):
            tokens.update(cjk_ngrams(token, stop_tokens=blocked))
    return tokens


def ordered_prompt_tokens(
    value: str,
    *,
    stop_tokens: set[str] | None = None,
) -> list[str]:
    blocked = stop_tokens or set()
    tokens: list[str] = []
    for match in TOKEN_RE.finditer(str(value or "").casefold()):
        token = match.group(0)
        if len(token) >= 2 and token not in blocked and token not in tokens:
            tokens.append(token)
    return tokens


def cjk_ngrams(value: str, *, stop_tokens: set[str] | None = STOP_TOKENS) -> set[str]:
    blocked = stop_tokens or set()
    grams: set[str] = set()
    chars = [char for char in value if CJK_RE.match(char)]
    for width in (3, 4, 5, 6):
        if len(chars) < width:
            continue
        grams.update(
            "".join(chars[index : index + width]) for index in range(len(chars) - width + 1)
        )
    return grams - blocked


def prompt_similarity_fingerprint(content: str) -> str:
    return " ".join(ordered_prompt_tokens(content))


def prompt_content_hash(content: str, *, min_chars: int = 80) -> str:
    normalized = " ".join(str(content or "").casefold().split())
    if len(normalized) < min_chars:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def prompt_title_key(title: str, *, max_tokens: int = 8) -> str:
    return " ".join(ordered_prompt_tokens(title)[:max_tokens])
