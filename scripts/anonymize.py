from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.anonymizer import anonymize_rows, load_terms
from src.data_io import iter_jsonl, write_json, write_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(description="Anonymize normalized Discord JSONL locally.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/ingested.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/anonymized.jsonl"))
    parser.add_argument("--summary", type=Path, default=Path("data/processed/anonymization_summary.json"))
    parser.add_argument("--target-author", help="Exact target display name or username before anonymization.")
    parser.add_argument("--target-author-id", help="Exact target Discord author id before anonymization.")
    parser.add_argument("--terms-file", type=Path, help="Optional private terms/places file, one per line.")
    parser.add_argument("--salt", default="", help="Optional stable salt for placeholder ids.")
    args = parser.parse_args()

    if not args.target_author and not args.target_author_id:
        parser.error("--target-author or --target-author-id is required to mark learned replies")

    rows = list(iter_jsonl(args.input))
    anonymized, summary = anonymize_rows(
        rows,
        target_author=args.target_author,
        target_author_id=args.target_author_id,
        custom_terms=load_terms(args.terms_file),
        salt=args.salt,
    )
    written = write_jsonl(args.output, anonymized)
    write_json(args.summary, summary)
    target_rows = sum(1 for row in anonymized if row.get("is_target"))
    print(f"anonymized_rows={written}")
    print(f"target_rows={target_rows}")
    print(f"summary={args.summary}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
