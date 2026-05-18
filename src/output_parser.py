from __future__ import annotations

import json
import re
from typing import Any

from .message_splitter import split_plain_text


def parse_strict_messages(raw_text: str, *, max_messages: int = 8) -> tuple[list[str], bool]:
    """Return messages and whether the model already produced valid target JSON."""
    payload = _extract_json(raw_text)
    if isinstance(payload, dict) and isinstance(payload.get("messages"), list):
        messages = [_clean_message(item) for item in payload["messages"]]
        cleaned = [message for message in messages if message]
        return cleaned[:max_messages], True

    repaired = _repair_jsonish_messages(raw_text)
    if repaired:
        return repaired[:max_messages], False

    return split_plain_text(raw_text, max_messages=max_messages), False


def messages_json(messages: list[str]) -> str:
    return json.dumps({"messages": messages}, ensure_ascii=False, separators=(",", ":"))


def _extract_json(text: str) -> Any:
    stripped = text.strip()
    candidates = [stripped]
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        candidates.insert(0, fenced.group(1))
    first = stripped.find("{")
    last = stripped.rfind("}")
    if first >= 0 and last > first:
        candidates.append(stripped[first : last + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _repair_jsonish_messages(text: str) -> list[str]:
    messages_match = re.search(r"messages\s*[:=]\s*\[(.*?)\]", text, flags=re.DOTALL | re.IGNORECASE)
    if not messages_match:
        return []
    body = messages_match.group(1)
    quoted = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"|\'([^\'\\]*(?:\\.[^\'\\]*)*)\'', body)
    messages: list[str] = []
    for double, single in quoted:
        raw = double or single
        try:
            value = json.loads(f'"{raw}"')
        except json.JSONDecodeError:
            value = raw
        cleaned = _clean_message(value)
        if cleaned:
            messages.append(cleaned)
    return messages


def _clean_message(value: object) -> str:
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text[:800].rstrip()
