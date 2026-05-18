from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from .conversation_features import build_conversation_hints, detect_abbreviations, detect_intent, detect_language, load_abbreviations
from .data_io import read_json
from .example_selector import load_example_bank, select_relevant_examples
from .model_client import ModelClientError, OpenAICompatibleClient, OpenAICompatibleConfig
from .output_parser import messages_json, parse_strict_messages
from .prompt_builder import build_chat_messages, load_fewshot_examples, load_history
from .social_engine import (
    PersonMemory,
    analyze_message,
    decide_reply,
    load_social_state,
    save_social_state,
    social_prompt_block,
    update_social_state,
)


DEFAULT_STYLE_PROFILE = Path("data/processed/style_profile.json")
DEFAULT_FEWSHOTS = Path("data/processed/fewshot_examples.json")
DEFAULT_EXAMPLE_BANK = Path("data/processed/conversations.cleaned.jsonl")
DEFAULT_SOCIAL_STATE = Path("state/social_state.json")
DEFAULT_ABBREVIATIONS = Path("config/abbreviations.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local Discord-style CLI for OpenAI-compatible endpoints.")
    parser.add_argument("message", nargs="*", help="Message to answer. If omitted, stdin is used.")
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1"))
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "qwen3.6-27b"))
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY", "local-not-needed"))
    parser.add_argument("--style-profile", type=Path, default=DEFAULT_STYLE_PROFILE)
    parser.add_argument("--fewshots", type=Path, default=DEFAULT_FEWSHOTS)
    parser.add_argument("--fewshot-limit", type=int, default=6)
    parser.add_argument("--example-bank", type=Path, default=DEFAULT_EXAMPLE_BANK)
    parser.add_argument("--abbreviations", type=Path, default=DEFAULT_ABBREVIATIONS)
    parser.add_argument("--no-dynamic-fewshots", action="store_true")
    parser.add_argument("--context", action="append", default=[], help="Recent history line, repeatable.")
    parser.add_argument("--history", type=Path, help="Optional text or JSONL history file.")
    parser.add_argument("--social-state", type=Path, default=DEFAULT_SOCIAL_STATE)
    parser.add_argument("--no-social", action="store_true")
    parser.add_argument("--user-id", default="local_user")
    parser.add_argument("--display-name", default="USER")
    parser.add_argument("--conversation-id", default="local_cli")
    parser.add_argument("--bot-name", action="append", default=["human", "bot"])
    parser.add_argument("--server-channel", action="store_true", help="Treat input as a server channel, not a DM.")
    parser.add_argument("--mentioned", action="store_true", help="Mark the bot as explicitly mentioned.")
    parser.add_argument("--force-reply", action="store_true")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--max-tokens", type=int, default=160)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--think", action="store_true", help="Allow invisible reasoning in prompt wording.")
    parser.add_argument("--no-think", action="store_true", help="Ask the model for no visible reasoning.")
    parser.add_argument("--mock", action="store_true", help="Offline mock mode; no model request is sent.")
    parser.add_argument("--chat", "--interactive", action="store_true", help="Start an interactive chat loop.")
    parser.add_argument("--json", action="store_true", help="Print normalized JSON instead of Discord-style lines.")
    parser.add_argument("--raw", action="store_true", help="Print raw model text before parsing.")
    parser.add_argument("--no-response-format", action="store_true", help="Do not send response_format to the endpoint.")
    args = parser.parse_args(argv)

    style_profile = _read_optional_json(args.style_profile)
    abbreviations = load_abbreviations(args.abbreviations)
    static_fewshots = load_fewshot_examples(args.fewshots, limit=args.fewshot_limit)
    example_bank = [] if args.no_dynamic_fewshots else load_example_bank(args.example_bank)
    history = [*load_history(args.history), *args.context]
    thinking = args.think and not args.no_think
    social_state = None if args.no_social else load_social_state(args.social_state)

    client = None
    if not args.mock:
        client = OpenAICompatibleClient(
            OpenAICompatibleConfig.from_env().with_overrides(
                base_url=args.base_url,
                api_key=args.api_key,
                model=args.model,
                timeout_seconds=args.timeout,
            )
        )

    if args.chat:
        return _chat_loop(
            args,
            client=client,
            style_profile=style_profile,
            static_fewshots=static_fewshots,
            example_bank=example_bank,
            abbreviations=abbreviations,
            history=history,
            thinking=thinking,
            social_state=social_state,
        )

    user_message = " ".join(args.message).strip() or sys.stdin.read().strip()
    if not user_message:
        parser.error("message is required via argument/stdin, or use --chat")

    try:
        raw = _generate_raw(
            args,
            client,
            user_message,
            history,
            style_profile,
            static_fewshots,
            example_bank,
            abbreviations,
            thinking,
            social_state,
        )
    except ModelClientError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.raw:
        print(raw)
        return 0

    messages, _was_strict = parse_strict_messages(raw)
    if not messages:
        return 0

    if args.json:
        print(messages_json(messages))
    else:
        for message in messages:
            print(message)
    return 0


def _chat_loop(
    args,
    *,
    client,
    style_profile: dict | None,
    static_fewshots: list[dict],
    example_bank: list[dict],
    abbreviations: dict[str, str],
    history: list[str],
    thinking: bool,
    social_state,
) -> int:
    print("Human style chat. Tape /exit pour quitter, /reset pour vider l'historique.")
    if args.mock:
        print("Mode mock offline actif.")
    while True:
        try:
            user_message = input("toi> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not user_message:
            continue
        if user_message in {"/exit", "/quit"}:
            return 0
        if user_message == "/reset":
            history.clear()
            print("historique vidé")
            continue
        try:
            raw = _generate_raw(
                args,
                client,
                user_message,
                history,
                style_profile,
                static_fewshots,
                example_bank,
                abbreviations,
                thinking,
                social_state,
            )
        except ModelClientError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        messages, _was_strict = parse_strict_messages(raw)
        if not messages:
            continue
        history.append(f"USER: {user_message}")
        for message in messages:
            print(f"me> {message}")
            history.append(f"ME: {message}")
        del history[:-40]
        if social_state is not None:
            save_social_state(args.social_state, social_state)


def _generate_raw(
    args,
    client,
    user_message: str,
    history: list[str],
    style_profile: dict | None,
    static_fewshots: list[dict],
    example_bank: list[dict],
    abbreviations: dict[str, str],
    thinking: bool,
    social_state,
) -> str:
    social_context = None
    analysis = decision = person = None
    if social_state is not None:
        analysis = analyze_message(
            user_message,
            bot_names=args.bot_name,
            is_dm=not args.server_channel,
            mentioned=args.mentioned,
            user_id=args.user_id,
            state=social_state,
        )
        person = social_state.people.setdefault(args.user_id, PersonMemory(user_id=args.user_id, display_name=args.display_name))
        decision = decide_reply(analysis, social_state, person)
        if not decision.should_reply and not args.force_reply:
            update_social_state(
                social_state,
                user_id=args.user_id,
                display_name=args.display_name,
                conversation_id=args.conversation_id,
                text=user_message,
                analysis=analysis,
                replied=False,
            )
            return messages_json([])
        social_context = social_prompt_block(analysis, decision, person, social_state)
    if args.mock:
        if social_state is not None and analysis is not None:
            update_social_state(
                social_state,
                user_id=args.user_id,
                display_name=args.display_name,
                conversation_id=args.conversation_id,
                text=user_message,
                analysis=analysis,
                replied=True,
            )
            save_social_state(args.social_state, social_state)
        return _mock_response(user_message)
    detected_abbreviations = detect_abbreviations(user_message, abbreviations)
    detected_intent = detect_intent(user_message, detected_abbreviations)
    detected_language = detect_language("\n".join([*history[-6:], user_message]))
    conversation_hints = build_conversation_hints(user_message, history, abbreviations)
    dynamic = select_relevant_examples(
        example_bank,
        user_message=user_message,
        history=history,
        language=detected_language,
        intent=detected_intent,
        limit=args.fewshot_limit,
    )
    fewshots = dynamic or static_fewshots[: args.fewshot_limit]
    raw = _call_model(args, client, user_message, history, style_profile, fewshots, thinking, social_context, conversation_hints)
    messages, _strict = parse_strict_messages(raw)
    if _bad_messages(messages, user_message):
        retry_history = [
            *history,
            (
                "SYSTEM_FEEDBACK: La réponse précédente était trop générique, répétée ou hors contexte. "
                "Réponds avec bon sens au dernier message, en style court Discord."
            ),
        ]
        raw = _call_model(args, client, user_message, retry_history, style_profile, fewshots[:3], thinking, social_context, conversation_hints)
    if social_state is not None and analysis is not None:
        update_social_state(
            social_state,
            user_id=args.user_id,
            display_name=args.display_name,
            conversation_id=args.conversation_id,
            text=user_message,
            analysis=analysis,
            replied=True,
        )
        save_social_state(args.social_state, social_state)
    return raw


def _call_model(
    args,
    client,
    user_message: str,
    history: list[str],
    style_profile: dict | None,
    fewshots: list[dict],
    thinking: bool,
    social_context: str | None,
    conversation_hints: str | None,
) -> str:
    prompt_messages = build_chat_messages(
        user_message=user_message,
        context=history,
        style_profile=style_profile,
        fewshot_examples=fewshots,
        thinking=thinking,
        social_context=social_context,
        conversation_hints=conversation_hints,
    )
    return client.chat(
        prompt_messages,
        temperature=args.temperature,
        top_p=args.top_p,
        max_tokens=args.max_tokens,
        response_format=not args.no_response_format,
    )


def _bad_messages(messages: list[str], user_message: str) -> bool:
    if not messages:
        return True
    lowered_user = _normalize_for_compare(user_message)
    lowered = [_normalize_for_compare(message) for message in messages]
    if lowered_user and any(message == lowered_user for message in lowered):
        return True
    if lowered_user and any(_token_overlap_ratio(message, lowered_user) >= 0.82 for message in lowered):
        return True
    if len(set(lowered)) < len(lowered):
        return True
    joined = " ".join(lowered)
    bad_short = {"cest la vie", "tfq", "...", "non", "pourquoi", "pq", "pk", "la vie"}
    if joined in bad_short and lowered_user not in {"ca va", "ça va", "cv"}:
        return True
    if lowered_user in {"pq", "pk", "pourquoi"} and joined in {"pourquoi", "pq", "pk"}:
        return True
    if lowered_user in {"tfq", "tu fais quoi"} and ("tfq" in lowered or "tu fais quoi" in lowered):
        return True
    if "?" in user_message and joined in {"ok", "okok", "ouais", "oe", "non"}:
        return True
    return False


def _normalize_for_compare(text: str) -> str:
    text = text.casefold().strip()
    text = text.replace("’", "'").replace("é", "e").replace("è", "e").replace("ê", "e").replace("à", "a").replace("ç", "c")
    text = re.sub(r"[^\w\s']", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _token_overlap_ratio(candidate: str, user_message: str) -> float:
    candidate_tokens = set(candidate.split())
    user_tokens = set(user_message.split())
    if not candidate_tokens or not user_tokens:
        return 0.0
    return len(candidate_tokens & user_tokens) / max(len(candidate_tokens), 1)


def _read_optional_json(path: Path | None) -> dict | None:
    if not path or not path.exists():
        return None
    payload = read_json(path)
    return payload if isinstance(payload, dict) else None


def _mock_response(user_message: str) -> str:
    lowered = user_message.casefold()
    if "?" in user_message or lowered.startswith(("tu ", "il ", "elle ", "on ")):
        return messages_json(["ouais attends", "je regarde ça"])
    if len(user_message) < 20:
        return messages_json(["okok", "jvois"])
    return messages_json(["ouais je capte", "faut que je check 2 sec"])


if __name__ == "__main__":
    raise SystemExit(main())
