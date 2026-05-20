from __future__ import annotations

import re
from collections import Counter
from statistics import mean
from typing import Any

ABBREVIATION_RE = re.compile(r"\b(?:jsp|mdr|ptdr|tkt|vrm|pq|pk|stp|svp|nn|oe|ouais|wsh|fr|btw|idk|ngl)\b", re.I)
WORD_RE = re.compile(r"[A-Za-zÀ-ÿ0-9_']+")


def build_style_profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
    target_messages = [str(row.get("content") or "") for row in rows if row.get("is_target")]
    lengths = [len(message) for message in target_messages]
    word_counts = [len(WORD_RE.findall(message)) for message in target_messages]
    bursts = _target_bursts(rows)
    tokens = _safe_tokens(target_messages)

    return {
        "target_message_count": len(target_messages),
        "avg_chars": round(mean(lengths), 2) if lengths else 0,
        "avg_words": round(mean(word_counts), 2) if word_counts else 0,
        "avg_messages_per_burst": round(mean(bursts), 2) if bursts else 0,
        "lowercase_start_ratio": _ratio(target_messages, lambda text: bool(text[:1].islower())),
        "question_ratio": _ratio(target_messages, lambda text: "?" in text),
        "exclamation_ratio": _ratio(target_messages, lambda text: "!" in text),
        "ellipsis_ratio": _ratio(target_messages, lambda text: "..." in text or "…" in text),
        "abbreviation_ratio": _ratio(target_messages, lambda text: bool(ABBREVIATION_RE.search(text))),
        "top_short_markers": tokens,
    }


def compare_style(reference: dict[str, Any], candidate_messages: list[str]) -> dict[str, Any]:
    candidate_rows = [{"is_target": True, "content": message} for message in candidate_messages]
    candidate = build_style_profile(candidate_rows)
    keys = ["avg_chars", "avg_words", "question_ratio", "exclamation_ratio", "abbreviation_ratio"]
    distances = {}
    for key in keys:
        ref = float(reference.get(key) or 0)
        cand = float(candidate.get(key) or 0)
        denom = max(abs(ref), 1.0)
        distances[key] = round(min(abs(ref - cand) / denom, 1.0), 4)
    score = round(1 - (sum(distances.values()) / len(distances)), 4) if distances else 0
    return {"score": score, "distances": distances, "candidate_profile": candidate}


def _target_bursts(rows: list[dict[str, Any]]) -> list[int]:
    bursts: list[int] = []
    current = 0
    for row in rows:
        if row.get("is_target"):
            current += 1
        elif current:
            bursts.append(current)
            current = 0
    if current:
        bursts.append(current)
    return bursts


def _safe_tokens(messages: list[str], limit: int = 30) -> list[str]:
    counter: Counter[str] = Counter()
    for message in messages:
        for token in WORD_RE.findall(message):
            token = token.casefold()
            if 2 <= len(token) <= 16 and not token.startswith("private_") and not token.startswith("user_"):
                counter[token] += 1
    return [token for token, _ in counter.most_common(limit)]


def _ratio(messages: list[str], predicate) -> float:
    if not messages:
        return 0.0
    return round(sum(1 for message in messages if predicate(message)) / len(messages), 4)

