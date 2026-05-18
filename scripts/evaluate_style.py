from __future__ import annotations

import argparse
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_io import iter_jsonl, read_json, write_json
from src.message_splitter import parse_model_messages
from src.style_profile import compare_style


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate prediction JSON message lists against style metrics.")
    parser.add_argument("--style-profile", type=Path, default=Path("data/processed/style_profile.json"))
    parser.add_argument("--predictions", type=Path, required=True, help="JSONL with messages/output or raw text.")
    parser.add_argument("--output", type=Path, default=Path("data/processed/evaluation.json"))
    args = parser.parse_args()

    reference = read_json(args.style_profile)
    rows = list(iter_jsonl(args.predictions))
    scores = []
    invalid = 0
    total_messages = 0
    for row in rows:
        messages = _row_messages(row)
        if not messages:
            invalid += 1
            continue
        total_messages += len(messages)
        scores.append(compare_style(reference, messages)["score"])

    report = {
        "rows": len(rows),
        "valid_rows": len(scores),
        "invalid_rows": invalid,
        "generated_messages": total_messages,
        "avg_style_score": round(mean(scores), 4) if scores else 0,
    }
    write_json(args.output, report)
    print(f"valid_rows={report['valid_rows']}")
    print(f"invalid_rows={report['invalid_rows']}")
    print(f"avg_style_score={report['avg_style_score']}")
    print(f"output={args.output}")
    return 0


def _row_messages(row: dict) -> list[str]:
    if isinstance(row.get("messages"), list):
        return [str(item) for item in row["messages"] if str(item).strip()]
    output = row.get("output")
    if isinstance(output, dict) and isinstance(output.get("messages"), list):
        return [str(item) for item in output["messages"] if str(item).strip()]
    raw = row.get("raw") or row.get("text")
    if isinstance(raw, str):
        return parse_model_messages(raw)
    if isinstance(row.get("json"), str):
        return parse_model_messages(row["json"])
    return []


if __name__ == "__main__":
    raise SystemExit(main())
