from __future__ import annotations

import hashlib
import random
import re
from collections import Counter
from dataclasses import dataclass
from statistics import mean
from typing import Any

ABBREVIATION_RE = re.compile(r"\b(?:jsp|mdr|ptdr|tkt|vrm|pq|pk|stp|svp|nn|oe|ouais|wsh|fr|btw|idk|ngl|jvois)\b", re.I)
WORD_RE = re.compile(r"[A-Za-zÀ-ÿ0-9_']+")
ENGLISH_HINTS = {
    "the",
    "and",
    "you",
    "that",
    "this",
    "what",
    "why",
    "ok",
    "okay",
    "check",
    "idk",
    "btw",
    "ngl",
}
FRENCH_HINTS = {
    "je",
    "tu",
    "il",
    "elle",
    "on",
    "nous",
    "vous",
    "pas",
    "que",
    "quoi",
    "ça",
    "cest",
    "c'est",
    "oui",
    "ouais",
    "non",
}
TIC_CANDIDATES = {
    "genre",
    "en vrai",
    "du coup",
    "jsp",
    "mdr",
    "ptdr",
    "wsh",
    "fr",
    "nan",
    "ouais",
    "tkt",
    "vrm",
    "2 sec",
    "jvois",
}


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    context: list[str]
    reference: list[str]


def parse_eval_rows(rows: list[dict[str, Any]]) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for index, row in enumerate(rows, start=1):
        context = _row_context(row)
        reference = _row_reference(row)
        if not reference:
            continue
        cases.append(
            EvalCase(
                case_id=str(row.get("id") or row.get("conversation_id") or f"eval_{index:06d}"),
                context=context,
                reference=reference,
            )
        )
    return cases


def evaluate_predictions(cases: list[EvalCase], predictions: dict[str, list[str]]) -> dict[str, Any]:
    per_case = []
    reference_profiles = []
    generated_profiles = []
    for case in cases:
        generated = predictions.get(case.case_id, [])
        reference_profile = text_profile(case.reference)
        generated_profile = text_profile(generated)
        reference_profiles.append(reference_profile)
        generated_profiles.append(generated_profile)
        per_case.append(
            {
                "case_id": case.case_id,
                "message_count_ref": len(case.reference),
                "message_count_gen": len(generated),
                "lexical_jaccard": lexical_jaccard(case.reference, generated),
                "tic_overlap": tic_overlap(case.reference, generated),
                "safe_preview_ref": safe_preview(case.reference),
                "safe_preview_gen": safe_preview(generated),
            }
        )

    aggregate = {
        "cases": len(cases),
        "generated_cases": sum(1 for case in cases if predictions.get(case.case_id)),
        "reference": aggregate_profiles(reference_profiles),
        "generated": aggregate_profiles(generated_profiles),
        "similarity": {
            "avg_lexical_jaccard": _mean([item["lexical_jaccard"] for item in per_case]),
            "avg_tic_overlap": _mean([item["tic_overlap"] for item in per_case]),
        },
    }
    return {"aggregate": aggregate, "cases": per_case}


def text_profile(messages: list[str]) -> dict[str, Any]:
    joined = "\n".join(messages)
    tokens = [token.casefold() for token in WORD_RE.findall(joined)]
    punctuation = Counter(char for char in joined if char in "?!.,;:…")
    tic_counts = {tic: _count_tic(joined, tic) for tic in TIC_CANDIDATES}
    tic_counts = {tic: count for tic, count in sorted(tic_counts.items()) if count}
    return {
        "message_count": len(messages),
        "avg_chars": round(_mean([len(message) for message in messages]), 4),
        "avg_words": round(_mean([len(WORD_RE.findall(message)) for message in messages]), 4),
        "abbreviation_rate": round(_ratio(messages, lambda text: bool(ABBREVIATION_RE.search(text))), 4),
        "punctuation_per_message": round(sum(punctuation.values()) / max(len(messages), 1), 4),
        "question_rate": round(_ratio(messages, lambda text: "?" in text), 4),
        "exclamation_rate": round(_ratio(messages, lambda text: "!" in text), 4),
        "french_hint_rate": round(_token_rate(tokens, FRENCH_HINTS), 4),
        "english_hint_rate": round(_token_rate(tokens, ENGLISH_HINTS), 4),
        "tic_counts": tic_counts,
        "lexical_tokens": sorted(set(tokens)),
    }


def aggregate_profiles(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    if not profiles:
        return {}
    tic_counter: Counter[str] = Counter()
    for profile in profiles:
        tic_counter.update(profile.get("tic_counts", {}))
    return {
        "avg_chars": round(_mean([profile["avg_chars"] for profile in profiles]), 4),
        "avg_words": round(_mean([profile["avg_words"] for profile in profiles]), 4),
        "avg_messages_per_response": round(_mean([profile["message_count"] for profile in profiles]), 4),
        "abbreviation_rate": round(_mean([profile["abbreviation_rate"] for profile in profiles]), 4),
        "punctuation_per_message": round(_mean([profile["punctuation_per_message"] for profile in profiles]), 4),
        "question_rate": round(_mean([profile["question_rate"] for profile in profiles]), 4),
        "exclamation_rate": round(_mean([profile["exclamation_rate"] for profile in profiles]), 4),
        "french_hint_rate": round(_mean([profile["french_hint_rate"] for profile in profiles]), 4),
        "english_hint_rate": round(_mean([profile["english_hint_rate"] for profile in profiles]), 4),
        "top_tics": dict(tic_counter.most_common(12)),
    }


def lexical_jaccard(reference: list[str], generated: list[str]) -> float:
    ref_tokens = set(text_profile(reference)["lexical_tokens"])
    gen_tokens = set(text_profile(generated)["lexical_tokens"])
    if not ref_tokens and not gen_tokens:
        return 1.0
    if not ref_tokens or not gen_tokens:
        return 0.0
    return round(len(ref_tokens & gen_tokens) / len(ref_tokens | gen_tokens), 4)


def tic_overlap(reference: list[str], generated: list[str]) -> float:
    ref_tics = set(text_profile(reference)["tic_counts"])
    gen_tics = set(text_profile(generated)["tic_counts"])
    if not ref_tics and not gen_tics:
        return 1.0
    if not ref_tics or not gen_tics:
        return 0.0
    return round(len(ref_tics & gen_tics) / len(ref_tics | gen_tics), 4)


def safe_preview(messages: list[str], *, chars: int = 24) -> list[str]:
    previews = []
    for message in messages[:2]:
        compact = " ".join(message.split())
        previews.append(compact[:chars] + ("…" if len(compact) > chars else ""))
    return previews


def build_blind_review(cases: list[EvalCase], predictions: dict[str, list[str]], *, seed: int = 13) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    rows = []
    for case in cases:
        generated = predictions.get(case.case_id)
        if not generated:
            continue
        items = [("reference", case.reference), ("generated", generated)]
        rng.shuffle(items)
        rows.append(
            {
                "review_id": hashlib.sha1(case.case_id.encode("utf-8")).hexdigest()[:12],
                "context_preview": safe_preview(case.context, chars=32),
                "A": safe_preview(items[0][1], chars=48),
                "B": safe_preview(items[1][1], chars=48),
                "answer_key": {"A": items[0][0], "B": items[1][0]},
                "human_choice": None,
            }
        )
    return rows


def markdown_report(report: dict[str, Any]) -> str:
    aggregate = report["aggregate"]
    ref = aggregate.get("reference", {})
    gen = aggregate.get("generated", {})
    sim = aggregate.get("similarity", {})
    lines = [
        "# Style Evaluation",
        "",
        "Rapport local. Les contenus sont limites a des micro-extraits tronques.",
        "",
        "## Summary",
        "",
        f"- Cases: {aggregate.get('cases', 0)}",
        f"- Generated cases: {aggregate.get('generated_cases', 0)}",
        f"- Avg lexical similarity: {sim.get('avg_lexical_jaccard', 0)}",
        f"- Avg tic overlap: {sim.get('avg_tic_overlap', 0)}",
        "",
        "## Aggregate Metrics",
        "",
        "| Metric | Reference | Generated |",
        "|---|---:|---:|",
    ]
    for key in [
        "avg_chars",
        "avg_words",
        "avg_messages_per_response",
        "abbreviation_rate",
        "punctuation_per_message",
        "question_rate",
        "exclamation_rate",
        "french_hint_rate",
        "english_hint_rate",
    ]:
        lines.append(f"| {key} | {ref.get(key, 0)} | {gen.get(key, 0)} |")
    lines.extend(["", "## Tics", "", f"- Reference: {_format_tics(ref.get('top_tics', {}))}", f"- Generated: {_format_tics(gen.get('top_tics', {}))}", ""])
    return "\n".join(lines)


def _row_context(row: dict[str, Any]) -> list[str]:
    context = row.get("context") or row.get("history") or []
    lines = []
    for item in context:
        if isinstance(item, str):
            lines.append(item)
        elif isinstance(item, dict):
            speaker = item.get("speaker") or item.get("author") or item.get("role") or "user"
            text = item.get("text") or item.get("content") or item.get("message")
            if text:
                lines.append(f"{speaker}: {text}")
    return lines


def _row_reference(row: dict[str, Any]) -> list[str]:
    if isinstance(row.get("target_messages"), list):
        return [str(item) for item in row["target_messages"] if str(item).strip()]
    output = row.get("output")
    if isinstance(output, dict) and isinstance(output.get("messages"), list):
        return [str(item) for item in output["messages"] if str(item).strip()]
    if isinstance(row.get("messages"), list):
        return [str(item) for item in row["messages"] if str(item).strip()]
    return []


def _count_tic(text: str, tic: str) -> int:
    return len(re.findall(re.escape(tic), text, flags=re.IGNORECASE))


def _ratio(messages: list[str], predicate) -> float:
    if not messages:
        return 0.0
    return sum(1 for message in messages if predicate(message)) / len(messages)


def _token_rate(tokens: list[str], hints: set[str]) -> float:
    if not tokens:
        return 0.0
    return sum(1 for token in tokens if token in hints) / len(tokens)


def _mean(values: list[float | int]) -> float:
    return mean(values) if values else 0.0


def _format_tics(tics: dict[str, int]) -> str:
    if not tics:
        return "none"
    return ", ".join(f"{tic}={count}" for tic, count in list(tics.items())[:8])
