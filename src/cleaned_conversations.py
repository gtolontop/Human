from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from .anonymizer import ADDRESS_RE, DISCORD_ID_RE, EMAIL_RE, INVITE_RE, MENTION_RE, PHONE_RE, URL_RE


@dataclass(frozen=True)
class CleanedConversationConfig:
    target_user_id: str | None = None
    target_username: str | None = None
    max_context_messages: int = 24
    reply_burst_minutes: int = 10


@dataclass
class ParticipantMap:
    target_user_id: str | None = None
    target_username: str | None = None
    labels: dict[str, str] = field(default_factory=dict)

    def is_target(self, row: dict[str, Any]) -> bool:
        author_id = str(row.get("author_id") or "").strip()
        author_name = str(row.get("author_name") or "").casefold()
        display_name = str(row.get("author_display_name") or "").casefold()
        if self.target_user_id and author_id == self.target_user_id:
            return True
        if self.target_username:
            expected = self.target_username.casefold()
            return expected in {author_name, display_name}
        return False

    def speaker_for(self, row: dict[str, Any]) -> str:
        if self.is_target(row):
            return "ME"
        key = str(row.get("author_id") or row.get("author_display_name") or row.get("author_name") or "unknown")
        if key not in self.labels:
            self.labels[key] = f"PERSON_{_letters(len(self.labels))}"
        return self.labels[key]


def build_cleaned_conversations(
    rows: list[dict[str, Any]],
    config: CleanedConversationConfig,
) -> list[dict[str, Any]]:
    participants = ParticipantMap(
        target_user_id=config.target_user_id,
        target_username=config.target_username,
    )
    visible_names = _participant_visible_names(rows, participants)
    usable_rows = [row for row in rows if _usable(row)]
    usable_rows.sort(key=lambda row: (row.get("timestamp") or "", row.get("source_message_id") or ""))

    conversations: list[dict[str, Any]] = []
    index = 0
    while index < len(usable_rows):
        row = usable_rows[index]
        if not participants.is_target(row):
            index += 1
            continue

        burst, next_index = _collect_reply_burst(usable_rows, index, participants, config)
        context_rows = _context_before(
            usable_rows,
            start_index=index,
            max_context_messages=config.max_context_messages,
        )
        if not context_rows:
            index = next_index
            continue

        conversation = {
            "conversation_id": f"discord_{len(conversations) + 1:06d}",
            "context": [
                {
                    "speaker": participants.speaker_for(item),
                    "text": clean_text(str(item.get("content") or ""), visible_names=visible_names),
                }
                for item in context_rows
            ],
            "target_messages": [
                clean_text(str(item.get("content") or ""), visible_names=visible_names)
                for item in burst
            ],
            "meta": {
                "source": "discord",
                "timestamps": [item.get("timestamp") for item in burst],
            },
        }
        conversations.append(conversation)
        index = next_index

    return conversations


def clean_text(text: str, *, visible_names: dict[str, str]) -> str:
    cleaned = text
    for name, replacement in sorted(visible_names.items(), key=lambda item: len(item[0]), reverse=True):
        cleaned = _replace_name(cleaned, name, replacement)
    cleaned = INVITE_RE.sub("<URL>", cleaned)
    cleaned = MENTION_RE.sub("<MENTION>", cleaned)
    cleaned = EMAIL_RE.sub("<EMAIL>", cleaned)
    cleaned = URL_RE.sub("<URL>", cleaned)
    cleaned = PHONE_RE.sub("<PHONE>", cleaned)
    cleaned = ADDRESS_RE.sub("<LOCATION>", cleaned)
    cleaned = DISCORD_ID_RE.sub("<DISCORD_ID>", cleaned)
    return cleaned


def _collect_reply_burst(
    rows: list[dict[str, Any]],
    start_index: int,
    participants: ParticipantMap,
    config: CleanedConversationConfig,
) -> tuple[list[dict[str, Any]], int]:
    burst = [rows[start_index]]
    cursor = start_index + 1
    last_timestamp = _parse_timestamp(rows[start_index].get("timestamp"))
    max_gap = timedelta(minutes=config.reply_burst_minutes)

    while cursor < len(rows):
        row = rows[cursor]
        if not participants.is_target(row):
            break
        current_timestamp = _parse_timestamp(row.get("timestamp"))
        if last_timestamp and current_timestamp and current_timestamp - last_timestamp > max_gap:
            break
        burst.append(row)
        last_timestamp = current_timestamp or last_timestamp
        cursor += 1
    return burst, cursor


def _context_before(rows: list[dict[str, Any]], *, start_index: int, max_context_messages: int) -> list[dict[str, Any]]:
    context: list[dict[str, Any]] = []
    cursor = start_index - 1
    while cursor >= 0 and len(context) < max_context_messages:
        context.append(rows[cursor])
        cursor -= 1
    context.reverse()
    return context


def _participant_visible_names(rows: list[dict[str, Any]], participants: ParticipantMap) -> dict[str, str]:
    replacements: dict[str, str] = {}
    for row in rows:
        speaker = participants.speaker_for(row)
        for key in ("author_name", "author_display_name"):
            name = str(row.get(key) or "").strip()
            if len(name) >= 2:
                replacements[name] = speaker
    return replacements


def _usable(row: dict[str, Any]) -> bool:
    return not bool(row.get("is_bot")) and bool(str(row.get("content") or "").strip())


def _parse_timestamp(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _replace_name(text: str, name: str, replacement: str) -> str:
    return text.replace(name, replacement)


def _letters(index: int) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    value = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, len(alphabet))
        value = alphabet[remainder] + value
    return value
