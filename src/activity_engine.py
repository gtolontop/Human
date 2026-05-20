from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_BACKGROUND: dict[str, Any] = {
    "persona": {
        "short_background": [
            "vit beaucoup sur le pc",
            "code des petits projets locaux",
            "traine sur Discord",
            "peut etre en cours selon l'heure",
            "repond souvent court et un peu sec quand il est occupe",
        ],
        "do_not_claim": [
            "ne pas inventer des noms de profs, lieux, entreprises ou personnes reelles",
            "ne pas dire etre une IA, un robot, ou un bot",
        ],
    },
    "activity_defaults": {
        "free": ["rien la", "sur le pc", "je chill"],
        "busy": ["j'suis occupé 2 sec", "je fais un truc vite fait", "att je finis un truc"],
        "tired": ["j'suis mort", "j'ai la flemme", "un peu fatigué"],
    },
    "activities": [
        {
            "id": "course",
            "label": "en cours",
            "status": ["j'suis en cours", "cours la", "j'écoute a moitié"],
            "when_asked": ["cours la", "j'suis en cours"],
            "availability": "slow",
        },
        {
            "id": "code",
            "label": "code",
            "status": ["je code un truc", "sur un projet la", "je debug un truc"],
            "when_asked": ["je code un truc", "je fix un truc"],
            "availability": "medium",
        },
        {
            "id": "pc",
            "label": "pc",
            "status": ["sur le pc", "je regarde un truc", "je traine"],
            "when_asked": ["sur le pc", "rien je traine"],
            "availability": "fast",
        },
        {
            "id": "game",
            "label": "jeu",
            "status": ["je joue un peu", "sur un jeu", "game vite fait"],
            "when_asked": ["je joue", "sur un jeu la"],
            "availability": "medium",
        },
        {
            "id": "sleepy",
            "label": "fatigue",
            "status": ["j'suis mort", "je vais dormir bientot", "j'ai trop la flemme"],
            "when_asked": ["j'suis mort", "rien je fatigue"],
            "availability": "slow",
        },
    ],
    "schedule": [
        {"days": ["mon", "tue", "wed", "thu", "fri"], "start": "08:00", "end": "12:00", "activity": "course"},
        {"days": ["mon", "tue", "wed", "thu", "fri"], "start": "13:30", "end": "17:30", "activity": "course"},
        {"days": ["mon", "tue", "wed", "thu", "fri"], "start": "18:00", "end": "22:30", "activity": "code"},
        {"days": ["sat", "sun"], "start": "12:00", "end": "18:00", "activity": "pc"},
        {"days": ["fri", "sat"], "start": "21:00", "end": "02:00", "activity": "game"},
        {"days": ["mon", "tue", "wed", "thu", "sun"], "start": "23:00", "end": "03:00", "activity": "sleepy"},
    ],
    "reactions": {
        "no_life_roast": ["mdrr abuse pas", "tais toi j'ai une vie", "j'ai une vie tqt", "j'suis juste sur le pc"],
        "activity_unknown": ["jsp la", "rien de fou", "sur un truc"],
    },
}

DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


@dataclass(frozen=True)
class ActivitySelection:
    activity_id: str
    label: str
    status: str
    availability: str
    source: str


def load_background(path: Path | None) -> dict[str, Any]:
    background = json.loads(json.dumps(DEFAULT_BACKGROUND))
    if not path or not path.exists():
        return background
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return background
    if isinstance(payload, dict):
        _deep_merge(background, payload)
    return background


def build_activity_context(
    background: dict[str, Any],
    *,
    user_message: str,
    history: list[str],
    intent: str,
    now: datetime | None = None,
) -> str:
    now = now or datetime.now().astimezone()
    selected = select_activity(background, now=now, history=history)
    persona = background.get("persona") if isinstance(background.get("persona"), dict) else {}
    short_background = _clean_list(persona.get("short_background"), limit=8)
    do_not_claim = _clean_list(persona.get("do_not_claim"), limit=6)
    reactions = background.get("reactions") if isinstance(background.get("reactions"), dict) else {}
    reaction_hint = _reaction_hint(user_message, reactions)
    lines = [
        f"time_local={now.strftime('%Y-%m-%d %H:%M')}",
        f"weekday={DAY_KEYS[now.weekday()]}",
        f"current_activity={selected.label}",
        f"activity_status={selected.status}",
        f"availability={selected.availability}",
        f"activity_source={selected.source}",
    ]
    if short_background:
        lines.append("background=" + " | ".join(short_background))
    if do_not_claim:
        lines.append("do_not_claim=" + " | ".join(do_not_claim))
    if reaction_hint:
        lines.append(f"reaction_hint={reaction_hint}")
    if intent == "activity_question":
        lines.append("activity_reply_rule=Si USER demande tfq/wyd, reponds avec current_activity/activity_status.")
    return "\n".join(lines)


def select_activity(background: dict[str, Any], *, now: datetime | None = None, history: list[str] | None = None) -> ActivitySelection:
    now = now or datetime.now().astimezone()
    activities = _activities_by_id(background)
    schedule = background.get("schedule") if isinstance(background.get("schedule"), list) else []
    day = DAY_KEYS[now.weekday()]
    minute = now.hour * 60 + now.minute
    for block in schedule:
        if not isinstance(block, dict):
            continue
        days = {str(item).lower()[:3] for item in block.get("days", [])}
        if day not in days:
            continue
        if _time_in_range(minute, str(block.get("start", "00:00")), str(block.get("end", "23:59"))):
            activity = activities.get(str(block.get("activity")))
            if activity:
                return _selection_from_activity(activity, now=now, source="schedule")
    activity_list = list(activities.values())
    if not activity_list:
        return ActivitySelection("free", "libre", "rien la", "fast", "fallback")
    seed = f"{now.date()}-{now.hour}-{history[-1] if history else ''}"
    index = int(hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8], 16) % len(activity_list)
    return _selection_from_activity(activity_list[index], now=now, source="rotating")


def _selection_from_activity(activity: dict[str, Any], *, now: datetime, source: str) -> ActivitySelection:
    statuses = _clean_list(activity.get("status") or activity.get("when_asked"), limit=12) or ["rien la"]
    index = int(hashlib.sha1(f"{activity.get('id')}:{now.date()}:{now.hour}".encode("utf-8")).hexdigest()[:8], 16) % len(statuses)
    return ActivitySelection(
        activity_id=str(activity.get("id") or "activity"),
        label=str(activity.get("label") or activity.get("id") or "activité"),
        status=statuses[index],
        availability=str(activity.get("availability") or "medium"),
        source=source,
    )


def _activities_by_id(background: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = background.get("activities") if isinstance(background.get("activities"), list) else []
    activities: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and row.get("id"):
            activities[str(row["id"])] = row
    return activities


def _reaction_hint(user_message: str, reactions: dict[str, Any]) -> str:
    lowered = user_message.casefold()
    no_life_terms = ("pas de vie", "no life", "nolife", "n'as pas de vie", "nas pas de vie")
    if any(term in lowered for term in no_life_terms):
        return _pick(_clean_list(reactions.get("no_life_roast"), limit=8), user_message) or "mdrr abuse pas"
    return ""


def _pick(items: list[str], seed: str) -> str:
    if not items:
        return ""
    index = int(hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8], 16) % len(items)
    return items[index]


def _time_in_range(minute: int, start: str, end: str) -> bool:
    start_minute = _parse_time(start)
    end_minute = _parse_time(end)
    if start_minute <= end_minute:
        return start_minute <= minute < end_minute
    return minute >= start_minute or minute < end_minute


def _parse_time(value: str) -> int:
    try:
        hour, minute = value.split(":", 1)
        return max(0, min(23, int(hour))) * 60 + max(0, min(59, int(minute)))
    except (ValueError, AttributeError):
        return 0


def _clean_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:limit]


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
