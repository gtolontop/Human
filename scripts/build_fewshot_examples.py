from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_io import iter_jsonl, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Select local anonymized fewshot examples for the style CLI.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/conversations.cleaned.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/fewshot_examples.json"))
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--min-context", type=int, default=1)
    args = parser.parse_args()

    examples = []
    for row in iter_jsonl(args.input):
        context = row.get("context")
        target_messages = row.get("target_messages")
        if not isinstance(context, list) or not isinstance(target_messages, list):
            continue
        if len(context) < args.min_context or not target_messages:
            continue
        examples.append({"context": context[-8:], "target_messages": target_messages[:6]})
        if len(examples) >= args.limit:
            break

    write_json(args.output, {"examples": examples})
    print(f"examples={len(examples)}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
