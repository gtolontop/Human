from __future__ import annotations

import argparse
from pathlib import Path

from src.data_io import iter_jsonl, write_json
from src.style_profile import build_style_profile


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a compact style profile from anonymized target messages.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/anonymized.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/style_profile.json"))
    args = parser.parse_args()

    rows = list(iter_jsonl(args.input))
    profile = build_style_profile(rows)
    write_json(args.output, profile)
    print(f"target_message_count={profile['target_message_count']}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

