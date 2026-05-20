from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.cli import (
    DEFAULT_ABBREVIATIONS,
    DEFAULT_BACKGROUND,
    DEFAULT_EXAMPLE_BANK,
    DEFAULT_FEWSHOTS,
    DEFAULT_SOCIAL_STATE,
    DEFAULT_STYLE_PROFILE,
    _generate_raw,
    _normalize_for_compare,
    _response_issue,
)
from src.activity_engine import load_background
from src.conversation_features import detect_abbreviations, detect_intent, detect_language, load_abbreviations
from src.data_io import read_json
from src.example_selector import load_example_bank
from src.model_client import ModelClientError, OpenAICompatibleClient, OpenAICompatibleConfig
from src.output_parser import parse_strict_messages
from src.prompt_builder import load_fewshot_examples


SCENARIOS: list[dict[str, Any]] = [
    {
        "name": "smalltalk_fr",
        "turns": [
            {"text": "salut", "expect_any": ["salut", "yo", "cc", "coucou"]},
            {"text": "cv?", "expect_any": ["cv", "ca va", "ça va", "bien", "bof", "ouais", "oui", "non", "tranquille", "good", "top"]},
            {"text": "tfq", "expect_any": ["rien", "pc", "jeu", "joue", "regarde", "check", "code", "bosse", "chill", "cours", "repose", "marche"]},
            "ah ok",
            "moi j'ai rien fait ajd",
            {"text": "viens vocal apres ?", "expect_any": ["oui", "ouais", "oe", "apres", "après", "plus tard", "non", "jsp", "maintenant", "quelle", "20h", "12h"]},
        ],
    },
    {
        "name": "short_slang",
        "turns": [
            {"text": "yo ma boy", "expect_any": ["yo", "hey", "salut", "wsh"]},
            {"text": "cdq ce truc", "expect_any": ["quoi", "jsp", "cest", "c'est", "ca", "ça", "?"]},
            {
                "text": "pq t'es parti hier",
                "expect_any": [
                    "jsp",
                    "parce",
                    "jdevais",
                    "devais",
                    "fatigue",
                    "parti",
                    "trucs",
                    "faire",
                    "tard",
                    "réunion",
                    "reunion",
                    "zzz",
                    "dormi",
                    "dormir",
                    "conneries",
                    "lourd",
                    "ennuyé",
                    "ennuye",
                    "taf",
                    "malade",
                    "deconnecte",
                    "déconnecté",
                ],
            },
            "raoe lourd",
            "tkt laisse",
            {
                "text": "bruhhh bro n'as pas de vie",
                "expect_any": ["mdr", "mdrr", "abuse", "tais", "vie", "tqt", "pc"],
                "forbid_any": ["its true", "c'est vrai", "cest vrai", "je vis dans ma vie"],
            },
        ],
    },
    {
        "name": "mixed_en",
        "turns": [
            {"text": "hey bro", "expect_any": ["yo", "hey", "hi", "sup"]},
            {"text": "how are you", "expect_any": ["good", "fine", "ok", "tired", "idk", "u", "you", "oui", "cv"]},
            {"text": "what u doing rn", "expect_any": ["nothing", "chill", "playing", "watching", "pc", "rn", "eating", "coding", "working"]},
            "that was kinda weird ngl",
            "ok fair",
        ],
    },
    {
        "name": "long_context_short_replies",
        "turns": [
            "j'ai eu une journée longue de ouf j'ai dormi 3h et apres y'avait encore des trucs a faire",
            {
                "text": "tu repondrais quoi a ça toi",
                "expect_any": ["jsp", "genre", "dis", "dit", "dirais", "reponds", "réponds", "réponse", "reponse", "peut", "dormirais", "dormir", "simple"],
                "forbid_any": ["sport", "foot", "dormi 3h", "pas de vie", "sur pc", "fais rien", "merde"],
            },
            "en vrai j'ai pas envie de faire un pavé",
            "mais faut pas que ça soit froid non plus",
            "tu captes ?",
        ],
    },
    {
        "name": "help_and_emotion",
        "turns": [
            {"text": "tu peux m'aider vite fait ?", "expect_any": ["oui", "ouais", "oe", "vasy", "vas y", "dis", "quoi", "sure", "go"]},
            "j'arrive pas a expliquer un truc sans faire trop sec",
            {"text": "t faché ou quoi ?", "expect_any": ["non", "nan", "pas", "bof", "jsp"]},
            "ok nickel",
            {"text": "tu peux check ça apres ?", "expect_any": ["oui", "ouais", "oe", "apres", "après", "jcheck", "check"]},
        ],
    },
    {
        "name": "fast_back_and_forth",
        "turns": [
            "yo",
            "att",
            "nan mais laisse",
            "enfait si",
            {"text": "tu viens ou pas", "expect_any": ["oui", "ouais", "oe", "non", "nan", "si", "apres", "après", "jsp", "viens", "jarrive", "att", "20h", "12h"]},
        ],
    },
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run synthetic local chat probes against the style CLI.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--api-key", default="yourbot-local")
    parser.add_argument("--model", default="qwen3.6-27b")
    parser.add_argument("--limit", type=int, default=0, help="Max scenarios to run, 0 means all.")
    parser.add_argument("--temperature", type=float, default=0.5)
    parser.add_argument("--top-p", type=float, default=0.88)
    parser.add_argument("--max-tokens", type=int, default=96)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--output-json", type=Path, default=Path("reports/chat_probe.json"))
    parser.add_argument("--output-md", type=Path, default=Path("reports/chat_probe.md"))
    args = parser.parse_args()

    cli_args = SimpleNamespace(
        base_url=args.base_url,
        api_key=args.api_key,
        model=args.model,
        timeout=args.timeout,
        temperature=args.temperature,
        top_p=args.top_p,
        max_tokens=args.max_tokens,
        no_response_format=True,
        mock=False,
        social_state=DEFAULT_SOCIAL_STATE,
        no_social=True,
        user_id="probe_user",
        display_name="PROBE",
        conversation_id="probe_dm",
        bot_name=["human", "bot"],
        server_channel=False,
        mentioned=False,
        force_reply=True,
        abbreviations=DEFAULT_ABBREVIATIONS,
        fewshot_limit=6,
    )
    client = OpenAICompatibleClient(
        OpenAICompatibleConfig.from_env().with_overrides(
            base_url=args.base_url,
            api_key=args.api_key,
            model=args.model,
            timeout_seconds=args.timeout,
        )
    )
    style_profile = _read_optional_json(DEFAULT_STYLE_PROFILE)
    abbreviations = load_abbreviations(DEFAULT_ABBREVIATIONS)
    background = load_background(DEFAULT_BACKGROUND)
    static_fewshots = load_fewshot_examples(DEFAULT_FEWSHOTS, limit=6)
    example_bank = load_example_bank(DEFAULT_EXAMPLE_BANK)

    scenarios = SCENARIOS[: args.limit] if args.limit else SCENARIOS
    results = []
    for scenario in scenarios:
        history: list[str] = []
        previous_assistant = ""
        turn_results = []
        for turn_spec in scenario["turns"]:
            user_message = turn_spec["text"] if isinstance(turn_spec, dict) else str(turn_spec)
            try:
                raw = _generate_raw(
                    cli_args,
                    client,
                    user_message,
                    history,
                    style_profile,
                    static_fewshots,
                    example_bank,
                    abbreviations,
                    background,
                    False,
                    None,
                )
                messages, strict = parse_strict_messages(raw)
                model_error = None
            except ModelClientError as exc:
                messages, strict, model_error = [], False, str(exc)
            issue = _judge(user_message, messages, previous_assistant, abbreviations, turn_spec)
            turn_results.append(
                {
                    "user": user_message,
                    "messages": messages,
                    "intent": detect_intent(user_message, detect_abbreviations(user_message, abbreviations)),
                    "language": detect_language(user_message),
                    "strict_json": strict,
                    "issue": issue,
                    "error": model_error,
                }
            )
            history.append(f"USER: {user_message}")
            for message in messages:
                history.append(f"ME: {message}")
            del history[:-40]
            previous_assistant = "\n".join(messages)
        results.append({"name": scenario["name"], "turns": turn_results})

    summary = _summary(results)
    payload = {"summary": summary, "scenarios": results}
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output_md.write_text(_markdown(payload), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json={args.output_json}")
    print(f"md={args.output_md}")
    return 0 if summary["issues"] == 0 else 1


def _judge(
    user_message: str,
    messages: list[str],
    previous_assistant: str,
    abbreviations: dict[str, str],
    turn_spec: Any,
) -> str | None:
    intent = detect_intent(user_message, detect_abbreviations(user_message, abbreviations))
    issue = _response_issue(messages, user_message, intent)
    if issue:
        return issue
    if len(messages) > 4:
        return "too_many_messages"
    if any(len(message) > 140 for message in messages):
        return "message_too_long"
    joined = _normalize_for_compare(" ".join(messages))
    if previous_assistant and joined == _normalize_for_compare(previous_assistant):
        return "repeat_previous_answer"
    if intent == "greeting" and any(token in joined.split() for token in {"wtf", "fdp", "gueule"}):
        return "greeting_too_aggressive"
    if isinstance(turn_spec, dict) and turn_spec.get("expect_any"):
        expected = [_normalize_for_compare(str(item)) for item in turn_spec["expect_any"]]
        if not any(item and item in joined for item in expected):
            return "missing_expected_semantic"
    if isinstance(turn_spec, dict) and turn_spec.get("forbid_any"):
        forbidden = [_normalize_for_compare(str(item)) for item in turn_spec["forbid_any"]]
        if any(item and item in joined for item in forbidden):
            return "forbidden_semantic"
    return None


def _summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = 0
    issues: dict[str, int] = {}
    message_counts: list[int] = []
    char_counts: list[int] = []
    for scenario in results:
        for turn in scenario["turns"]:
            total += 1
            messages = turn["messages"]
            message_counts.append(len(messages))
            char_counts.extend(len(message) for message in messages)
            if turn["issue"]:
                issues[turn["issue"]] = issues.get(turn["issue"], 0) + 1
            if turn["error"]:
                issues["model_error"] = issues.get("model_error", 0) + 1
    return {
        "turns": total,
        "issues": sum(issues.values()),
        "issue_types": issues,
        "avg_messages": round(sum(message_counts) / max(len(message_counts), 1), 2),
        "avg_chars": round(sum(char_counts) / max(len(char_counts), 1), 2),
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Chat Probe",
        "",
        "Synthetic local probes only. No private dataset excerpts.",
        "",
        "```json",
        json.dumps(payload["summary"], ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    for scenario in payload["scenarios"]:
        lines.append(f"## {scenario['name']}")
        for turn in scenario["turns"]:
            status = "OK" if not turn["issue"] and not turn["error"] else f"ISSUE: {turn['issue'] or turn['error']}"
            lines.append(f"- USER `{turn['user']}` -> {status}; messages={len(turn['messages'])}")
        lines.append("")
    return "\n".join(lines)


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = read_json(path)
    return payload if isinstance(payload, dict) else None


if __name__ == "__main__":
    raise SystemExit(main())
