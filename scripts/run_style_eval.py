from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.cli import _mock_response
from src.data_io import iter_jsonl, read_json, write_json, write_jsonl
from src.model_client import ModelClientError, OpenAICompatibleClient, OpenAICompatibleConfig
from src.output_parser import parse_strict_messages
from src.prompt_builder import build_chat_messages, load_fewshot_examples
from src.style_eval import build_blind_review, evaluate_predictions, markdown_report, parse_eval_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and evaluate local style responses.")
    parser.add_argument("--eval", type=Path, default=Path("data/processed/eval.jsonl"))
    parser.add_argument("--style-profile", type=Path, default=Path("data/processed/style_profile.json"))
    parser.add_argument("--fewshots", type=Path, default=Path("data/processed/fewshot_examples.json"))
    parser.add_argument("--fewshot-limit", type=int, default=4)
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1"))
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "qwen3.6-27b"))
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY", "local-not-needed"))
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--limit", type=int, default=0, help="Limit eval cases; 0 means all.")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--think", action="store_true")
    parser.add_argument("--no-response-format", action="store_true")
    parser.add_argument("--report-json", type=Path, default=Path("reports/eval_style.json"))
    parser.add_argument("--report-md", type=Path, default=Path("reports/eval_style.md"))
    parser.add_argument("--blind-review", action="store_true")
    parser.add_argument("--blind-output", type=Path, default=Path("reports/blind_review.jsonl"))
    args = parser.parse_args()

    rows = list(iter_jsonl(args.eval))
    cases = parse_eval_rows(rows)
    if args.limit > 0:
        cases = cases[: args.limit]
    if not cases:
        parser.error("eval file contains no usable cases with target messages")

    style_profile = _read_optional_json(args.style_profile)
    fewshots = load_fewshot_examples(args.fewshots, limit=args.fewshot_limit)
    predictions = _generate_predictions(args, cases, style_profile, fewshots)
    report = evaluate_predictions(cases, predictions)
    write_json(args.report_json, report)
    args.report_md.parent.mkdir(parents=True, exist_ok=True)
    args.report_md.write_text(markdown_report(report), encoding="utf-8")

    print(f"cases={report['aggregate']['cases']}")
    print(f"generated_cases={report['aggregate']['generated_cases']}")
    print(f"report_json={args.report_json}")
    print(f"report_md={args.report_md}")

    if args.blind_review:
        blind_rows = build_blind_review(cases, predictions)
        write_jsonl(args.blind_output, blind_rows)
        print(f"blind_review={args.blind_output}")

    return 0


def _generate_predictions(args: argparse.Namespace, cases, style_profile, fewshots) -> dict[str, list[str]]:
    predictions: dict[str, list[str]] = {}
    client = None
    if not args.mock:
        config = OpenAICompatibleConfig.from_env().with_overrides(
            base_url=args.base_url,
            api_key=args.api_key,
            model=args.model,
            timeout_seconds=args.timeout,
        )
        client = OpenAICompatibleClient(config)

    for case in cases:
        user_message = case.context[-1] if case.context else "Réponds à ce contexte."
        prompt_messages = build_chat_messages(
            user_message=user_message,
            context=case.context[:-1],
            style_profile=style_profile,
            fewshot_examples=fewshots,
            thinking=args.think,
        )
        if args.mock:
            raw = _mock_response(user_message)
        else:
            try:
                raw = client.chat(
                    prompt_messages,
                    temperature=args.temperature,
                    top_p=args.top_p,
                    max_tokens=args.max_tokens,
                    response_format=not args.no_response_format,
                )
            except ModelClientError as exc:
                print(f"warning: skipped case {case.case_id}: {exc}", file=sys.stderr)
                continue
        messages, _strict = parse_strict_messages(raw)
        predictions[case.case_id] = messages
    return predictions


def _read_optional_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    payload = read_json(path)
    return payload if isinstance(payload, dict) else None


if __name__ == "__main__":
    raise SystemExit(main())
