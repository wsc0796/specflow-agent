"""Deterministic keyword extraction from requirement text."""

from __future__ import annotations

import re

_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "can",
        "shall",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "under",
        "and",
        "but",
        "or",
        "not",
        "no",
        "if",
        "then",
        "else",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "we",
        "you",
        "they",
        "he",
        "she",
        "add",
        "need",
        "want",
        "implement",
        "create",
        "make",
        "use",
        "using",
        "provide",
        "support",
        "ensure",
        "功能",
        "需要",
        "实现",
        "添加",
        "增加",
        "支持",
        "提供",
        "使用",
        "一个",
        "这个",
        "那个",
        "可以",
        "应该",
        "能够",
        "进行",
        "以及",
        "或者",
        "并且",
        "的",
        "了",
        "是",
        "在",
        "和",
        "与",
        "为",
    }
)

_CODE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("snake_case", re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")),
    ("CamelCase", re.compile(r"\b[A-Z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*\b")),
    ("kebab-case", re.compile(r"\b[a-z][a-z0-9]*(?:-[a-z0-9]+)+\b")),
    ("dot.path", re.compile(r"\b[a-z][a-z0-9]*(?:\.[a-z0-9]+)+\b")),
]

_CHINESE_WORD_RE = re.compile(r"[一-鿿]{2,6}")

# Small, deterministic domain aliases keep Chinese product requirements
# searchable in repositories whose identifiers are English.  This is an
# evidence-search aid, not translation or semantic inference.
_CHINESE_CODE_ALIASES = {
    "订单": "order",
    "超时": "timeout",
    "取消": "cancel",
    "状态": "status",
    "事务": "transaction",
    "幂等": "idempot",
    "测试": "test",
}


def extract_keywords(
    requirement: str,
    *,
    max_keywords: int = 10,
    technology_hints: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Extract deterministic search keywords from a requirement string."""
    scored: dict[str, float] = {}

    for label, pattern in _CODE_PATTERNS:
        for match in pattern.finditer(requirement):
            token = match.group()
            weight = 2.0 if label in {"CamelCase", "snake_case"} else 1.0
            scored[token] = scored.get(token, 0) + weight

    for match in _CHINESE_WORD_RE.finditer(requirement):
        token = match.group()
        if token not in _STOP_WORDS:
            scored[token] = scored.get(token, 0) + 1.5

    for chinese, code_term in _CHINESE_CODE_ALIASES.items():
        if chinese in requirement:
            scored[code_term] = scored.get(code_term, 0) + 2.0

    words = re.findall(r"[a-zA-Z][a-zA-Z0-9]{2,}", requirement)
    for word in words:
        lowered = word.lower()
        if lowered not in _STOP_WORDS and len(word) >= 3:
            scored[lowered] = scored.get(lowered, 0) + 1.0

    for hint in technology_hints:
        scored[hint] = scored.get(hint, 0) + 0.5

    ranked = sorted(scored.items(), key=lambda item: (-item[1], item[0]))
    result = [token for token, _ in ranked[:max_keywords]]
    return tuple(result)
