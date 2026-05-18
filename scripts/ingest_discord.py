from __future__ import annotations

import argparse
from pathlib import Path

from src.data_io import write_jsonl
from src.discord_export import load_discord_export


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest DiscordChatExporter JSON into normalized JSONL.")
    parser.add_argument("--input", type=Path, default=Path("data/raw"), help="JSON file or folder.")
    parser.add_argument("--output", type=Path, default=Path("data/processed/ingested.jsonl"))
    args = parser.parse_args()

    rows = load_discord_export(args.input)
    count = write_jsonl(args.output, rows)
    print(f"ingested_rows={count}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

