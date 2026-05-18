from __future__ import annotations

import argparse
from pathlib import Path

from src.data_io import iter_jsonl, write_jsonl
from src.dataset_builder import DatasetConfig, build_training_examples


def main() -> int:
    parser = argparse.ArgumentParser(description="Build supervised examples from anonymized Discord JSONL.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/anonymized.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/dataset.jsonl"))
    parser.add_argument("--max-context-messages", type=int, default=12)
    parser.add_argument("--max-response-messages", type=int, default=6)
    parser.add_argument("--min-context-messages", type=int, default=1)
    parser.add_argument("--exclude-target-context", action="store_true")
    args = parser.parse_args()

    rows = list(iter_jsonl(args.input))
    examples = build_training_examples(
        rows,
        DatasetConfig(
            max_context_messages=args.max_context_messages,
            max_response_messages=args.max_response_messages,
            min_context_messages=args.min_context_messages,
            include_target_in_context=not args.exclude_target_context,
        ),
    )
    count = write_jsonl(args.output, examples)
    print(f"examples={count}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

