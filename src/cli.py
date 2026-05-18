from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .data_io import read_json
from .model_client import ModelClientError, OpenAICompatibleClient, OpenAICompatibleConfig
from .output_parser import messages_json, parse_strict_messages
from .prompt_builder import build_chat_messages, load_fewshot_examples, load_history


DEFAULT_STYLE_PROFILE = Path("data/processed/style_profile.json")
DEFAULT_FEWSHOTS = Path("data/processed/fewshot_examples.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local Discord-style CLI for OpenAI-compatible endpoints.")
    parser.add_argument("message", nargs="*", help="Message to answer. If omitted, stdin is used.")
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1"))
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "qwen3.6-27b"))
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY", "local-not-needed"))
    parser.add_argument("--style-profile", type=Path, default=DEFAULT_STYLE_PROFILE)
    parser.add_argument("--fewshots", type=Path, default=DEFAULT_FEWSHOTS)
    parser.add_argument("--fewshot-limit", type=int, default=4)
    parser.add_argument("--context", action="append", default=[], help="Recent history line, repeatable.")
    parser.add_argument("--history", type=Path, help="Optional text or JSONL history file.")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--think", action="store_true", help="Allow invisible reasoning in prompt wording.")
    parser.add_argument("--no-think", action="store_true", help="Ask the model for no visible reasoning.")
    parser.add_argument("--mock", action="store_true", help="Offline mock mode; no model request is sent.")
    parser.add_argument("--json", action="store_true", help="Print normalized JSON instead of Discord-style lines.")
    parser.add_argument("--raw", action="store_true", help="Print raw model text before parsing.")
    parser.add_argument("--no-response-format", action="store_true", help="Do not send response_format to the endpoint.")
    args = parser.parse_args(argv)

    user_message = " ".join(args.message).strip() or sys.stdin.read().strip()
    if not user_message:
        parser.error("message is required via argument or stdin")

    style_profile = _read_optional_json(args.style_profile)
    fewshots = load_fewshot_examples(args.fewshots, limit=args.fewshot_limit)
    history = [*load_history(args.history), *args.context]
    thinking = args.think and not args.no_think
    prompt_messages = build_chat_messages(
        user_message=user_message,
        context=history,
        style_profile=style_profile,
        fewshot_examples=fewshots,
        thinking=thinking,
    )

    if args.mock:
        raw = _mock_response(user_message)
    else:
        config = OpenAICompatibleConfig.from_env().with_overrides(
            base_url=args.base_url,
            api_key=args.api_key,
            model=args.model,
            timeout_seconds=args.timeout,
        )
        client = OpenAICompatibleClient(config)
        try:
            raw = client.chat(
                prompt_messages,
                temperature=args.temperature,
                top_p=args.top_p,
                max_tokens=args.max_tokens,
                response_format=not args.no_response_format,
            )
        except ModelClientError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    if args.raw:
        print(raw)
        return 0

    messages, _was_strict = parse_strict_messages(raw)
    if not messages:
        print("error: model returned no usable messages", file=sys.stderr)
        return 3

    if args.json:
        print(messages_json(messages))
    else:
        for message in messages:
            print(message)
    return 0


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
