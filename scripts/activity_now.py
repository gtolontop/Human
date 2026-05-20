from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.activity_engine import build_activity_context, load_background
from src.conversation_features import detect_abbreviations, detect_intent, load_abbreviations
from src.cli import DEFAULT_ABBREVIATIONS, DEFAULT_BACKGROUND


def main() -> int:
    parser = argparse.ArgumentParser(description="Show the local background/activity prompt block.")
    parser.add_argument("message", nargs="*", default=["tfq"], help="Optional user message to classify.")
    parser.add_argument("--background", type=Path, default=DEFAULT_BACKGROUND)
    parser.add_argument("--abbreviations", type=Path, default=DEFAULT_ABBREVIATIONS)
    parser.add_argument("--at", help="Override local datetime, e.g. 2026-05-18T10:30:00")
    args = parser.parse_args()

    user_message = " ".join(args.message).strip() or "tfq"
    abbreviations = load_abbreviations(args.abbreviations)
    intent = detect_intent(user_message, detect_abbreviations(user_message, abbreviations))
    now = datetime.fromisoformat(args.at).astimezone() if args.at else None
    background = load_background(args.background)
    print(build_activity_context(background, user_message=user_message, history=[], intent=intent, now=now))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
