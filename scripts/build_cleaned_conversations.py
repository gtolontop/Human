from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.cleaned_conversations import CleanedConversationConfig, build_cleaned_conversations
from src.data_io import write_jsonl
from src.discord_export import load_discord_export


def main() -> int:
    parser = argparse.ArgumentParser(description="Build anonymized style conversations from Discord exports.")
    parser.add_argument("--input", type=Path, default=Path("data/raw"), help="DiscordChatExporter JSON file or folder.")
    parser.add_argument("--output", type=Path, default=Path("data/processed/conversations.cleaned.jsonl"))
    parser.add_argument("--target-user-id", help="Discord user id for the style owner.")
    parser.add_argument("--target-username", help="Discord username/display name for the style owner.")
    parser.add_argument("--max-context-messages", type=int, default=24)
    parser.add_argument("--reply-burst-minutes", type=int, default=10)
    args = parser.parse_args()

    if not args.target_user_id and not args.target_username:
        parser.error("--target-user-id or --target-username is required")

    rows = load_discord_export(args.input)
    conversations = build_cleaned_conversations(
        rows,
        CleanedConversationConfig(
            target_user_id=args.target_user_id,
            target_username=args.target_username,
            max_context_messages=args.max_context_messages,
            reply_burst_minutes=args.reply_burst_minutes,
        ),
    )
    count = write_jsonl(args.output, conversations)
    target_messages = sum(len(item["target_messages"]) for item in conversations)
    print(f"input_rows={len(rows)}")
    print(f"conversations={count}")
    print(f"target_messages={target_messages}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
