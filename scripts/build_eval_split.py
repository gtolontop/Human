from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_io import iter_jsonl, write_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a local eval.jsonl sample from cleaned conversations.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/conversations.cleaned.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/eval.jsonl"))
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rows = list(iter_jsonl(args.input))
    rng = random.Random(args.seed)
    rng.shuffle(rows)
    selected = rows[: args.limit] if args.limit > 0 else rows
    written = write_jsonl(args.output, selected)
    print(f"eval_cases={written}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
