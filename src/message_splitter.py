from __future__ import annotations

import json
import re
from typing import Any


MAX_MESSAGES = 8
MAX_MESSAGE_CHARS = 800


def parse_model_messages(raw_text: str, *, max_messages: int = MAX_MESSAGES) -> list[str]:
    """Parse the required model JSON: {"messages": ["...", "..."]}."""
    payload = _extract_json_object(raw_text)
    if payload is not None:
        messages = payload.get("messages")
        if isinstance(messages, list):
            cleaned = [_clean_message(item) for item in messages]
            return [message for message in cleaned if message][:max_messages]
    return split_plain_text(raw_text, max_messages=max_messages)


def split_plain_text(text: str, *, max_messages: int = MAX_MESSAGES) -> list[str]:
    text = text.strip()
    if not text:
        return []

    lines = [_clean_message(line) for line in text.splitlines() if _clean_message(line)]
    if len(lines) > 1:
        return lines[:max_messages]

    chunks = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý0-9])", text)
    cleaned = [_clean_message(chunk) for chunk in chunks if _clean_message(chunk)]
    if len(cleaned) > 1:
        return cleaned[:max_messages]

    return [_clean_message(text)]


def messages_to_json(messages: list[str]) -> str:
    return json.dumps({"messages": messages}, ensure_ascii=False)


def _extract_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    candidates = [stripped]
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        candidates.insert(0, fenced.group(1))
    first = stripped.find("{")
    last = stripped.rfind("}")
    if first != -1 and last != -1 and first < last:
        candidates.append(stripped[first : last + 1])

    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _clean_message(value: object) -> str:
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > MAX_MESSAGE_CHARS:
        text = text[:MAX_MESSAGE_CHARS].rstrip()
    return text

