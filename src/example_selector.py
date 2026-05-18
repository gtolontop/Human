from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .data_io import iter_jsonl
from .prompt_builder import load_fewshot_examples

WORD_RE = re.compile(r"[A-Za-zÀ-ÿ0-9_']+")
PLACEHOLDER_RE = re.compile(r"<[A-Z_]+>")
STOPWORDS = {
    "a",
    "au",
    "aux",
    "avec",
    "ce",
    "ces",
    "cest",
    "c'est",
    "dans",
    "de",
    "des",
    "du",
    "elle",
    "en",
    "et",
    "il",
    "je",
    "la",
    "le",
    "les",
    "me",
    "moi",
    "mon",
    "ne",
    "on",
    "ou",
    "pas",
    "pour",
    "que",
    "qui",
    "se",
    "sur",
    "ta",
    "te",
    "tes",
    "toi",
    "ton",
    "tu",
    "un",
    "une",
}


def load_example_bank(path: Path | None, *, limit: int = 5000) -> list[dict[str, Any]]:
    if not path or not path.exists():
        return []
    examples = load_fewshot_examples(path, limit=limit)
    return [example for example in examples if quality_score(example) >= 0.35]


def select_relevant_examples(
    bank: list[dict[str, Any]],
    *,
    user_message: str,
    history: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    if limit <= 0 or not bank:
        return []
    query_tokens = _tokens("\n".join([*history[-8:], user_message]))
    ranked = []
    for example in bank:
        context_text = "\n".join(example.get("context", [])[-8:])
        overlap = _jaccard(query_tokens, _tokens(context_text))
        score = quality_score(example) + (overlap * 1.6)
        if overlap > 0 or _short_intent_match(user_message, context_text):
            ranked.append((score, example))
    if not ranked:
        ranked = [(quality_score(example), example) for example in bank[:200]]
    ranked.sort(key=lambda item: item[0], reverse=True)
    selected: list[dict[str, Any]] = []
    seen_targets: set[str] = set()
    for _score, example in ranked:
        target_key = "\n".join(example.get("target_messages", [])).casefold()
        if target_key in seen_targets:
            continue
        seen_targets.add(target_key)
        selected.append(example)
        if len(selected) >= limit:
            break
    return selected


def quality_score(example: dict[str, Any]) -> float:
    context = [str(item).strip() for item in example.get("context", []) if str(item).strip()]
    targets = [str(item).strip() for item in example.get("target_messages", []) if str(item).strip()]
    if not context or not targets:
        return 0.0
    joined = "\n".join(targets)
    chars = [len(item) for item in targets]
    score = 0.55
    if 1 <= len(targets) <= 5:
        score += 0.15
    if 2 <= sum(chars) / len(chars) <= 80:
        score += 0.15
    if all(len(item) <= 160 for item in targets):
        score += 0.1
    if len(set(item.casefold() for item in targets)) == len(targets):
        score += 0.05
    if all(len(item) <= 2 for item in targets):
        score -= 0.35
    if PLACEHOLDER_RE.search(joined):
        score -= 0.25
    if _looks_degenerate(targets):
        score -= 0.35
    return max(0.0, min(score, 1.0))


def _looks_degenerate(messages: list[str]) -> bool:
    lowered = [message.casefold().strip() for message in messages]
    if len(set(lowered)) < len(lowered):
        return True
    joined = " ".join(lowered)
    if joined in {"c'est la vie", "tfq", "..."}:
        return True
    return False


def _tokens(text: str) -> set[str]:
    return {
        token.casefold()
        for token in WORD_RE.findall(text)
        if len(token) > 1 and token.casefold() not in STOPWORDS
    }


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _short_intent_match(user_message: str, context_text: str) -> bool:
    user = user_message.casefold().strip()
    context = context_text.casefold()
    if user in {"salut", "yo", "cc", "coucou", "wsh"}:
        return any(word in context for word in ("salut", "yo", "coucou", "wsh"))
    if user in {"tfq", "tu fais quoi", "tu fais quoi ?"}:
        return any(word in context for word in ("tfq", "tu fais quoi", "fais quoi"))
    if user in {"pq", "pourquoi"}:
        return any(word in context for word in ("pq", "pourquoi", "pk"))
    return False
