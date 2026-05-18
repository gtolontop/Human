from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.social_engine import (
    PersonMemory,
    analyze_message,
    decide_reply,
    load_social_state,
    save_social_state,
    social_prompt_block,
    update_social_state,
)


SCENARIOS = [
    {"user_id": "alice", "name": "Alice", "conversation": "dm_alice", "dm": True, "text": "salut ça va ?"},
    {"user_id": "bob", "name": "Bob", "conversation": "server_general", "dm": False, "text": "vous avez vu le truc mdr"},
    {"user_id": "bob", "name": "Bob", "conversation": "server_general", "dm": False, "mentioned": True, "text": "human tu peux check stp ?"},
    {"user_id": "chris", "name": "Chris", "conversation": "dm_chris", "dm": True, "text": "jpp ça me saoule"},
    {"user_id": "troll", "name": "Troll", "conversation": "server_general", "dm": False, "mentioned": True, "text": "tg t'es con"},
    {"user_id": "alice", "name": "Alice", "conversation": "dm_alice", "dm": True, "text": "tfq"},
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate multi-person Discord social state locally.")
    parser.add_argument("--state", type=Path, default=Path("state/social_state.sim.json"))
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--bot-name", action="append", default=["human", "bot"])
    args = parser.parse_args()

    if args.reset and args.state.exists():
        args.state.unlink()
    state = load_social_state(args.state)
    for event in SCENARIOS:
        person = state.people.setdefault(
            event["user_id"],
            PersonMemory(user_id=event["user_id"], display_name=event["name"]),
        )
        analysis = analyze_message(
            event["text"],
            bot_names=args.bot_name,
            is_dm=event.get("dm", False),
            mentioned=event.get("mentioned", False),
            user_id=event["user_id"],
            state=state,
        )
        decision = decide_reply(analysis, state, person)
        update_social_state(
            state,
            user_id=event["user_id"],
            display_name=event["name"],
            conversation_id=event["conversation"],
            text=event["text"],
            analysis=analysis,
            replied=decision.should_reply,
        )
        print(f"{event['name']}: intent={analysis.intent} tone={analysis.tone} addressed={analysis.addressing_bot} reply={decision.should_reply} style={decision.reply_style} delay={decision.delay_seconds}s")
        print(f"  social={social_prompt_block(analysis, decision, person, state)}")
    save_social_state(args.state, state)
    print(f"state={args.state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
