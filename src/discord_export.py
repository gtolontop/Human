from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .data_io import find_json_files, read_json


@dataclass(frozen=True)
class NormalizedMessage:
    source_file: str
    source_message_id: str | None
    channel_id: str | None
    channel_name: str | None
    timestamp: str | None
    author_id: str | None
    author_name: str
    author_display_name: str
    is_bot: bool
    content: str
    attachment_count: int
    embed_count: int

    def to_row(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "source_message_id": self.source_message_id,
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "timestamp": self.timestamp,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "author_display_name": self.author_display_name,
            "is_bot": self.is_bot,
            "content": self.content,
            "attachment_count": self.attachment_count,
            "embed_count": self.embed_count,
        }


def load_discord_export(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for json_path in find_json_files(path):
        payload = read_json(json_path)
        rows.extend(parse_discord_chat_exporter(payload, json_path))
    return rows


def parse_discord_chat_exporter(payload: Any, source_path: Path) -> list[dict[str, Any]]:
    messages, channel = _extract_messages_and_channel(payload)
    normalized: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        item = _normalize_message(message, channel, source_path)
        if item.content.strip():
            normalized.append(item.to_row())
    normalized.sort(key=lambda row: (row.get("timestamp") or "", row.get("source_message_id") or ""))
    return normalized


def _extract_messages_and_channel(payload: Any) -> tuple[list[Any], dict[str, Any]]:
    if isinstance(payload, list):
        return payload, {}
    if not isinstance(payload, dict):
        raise ValueError("Unsupported Discord export: expected a JSON object or list")
    messages = payload.get("messages") or payload.get("Messages")
    if not isinstance(messages, list):
        raise ValueError("Unsupported Discord export: missing messages array")
    channel = payload.get("channel") or payload.get("Channel") or {}
    if not isinstance(channel, dict):
        channel = {}
    return messages, channel


def _normalize_message(message: dict[str, Any], channel: dict[str, Any], source_path: Path) -> NormalizedMessage:
    author = message.get("author") or message.get("Author") or {}
    if not isinstance(author, dict):
        author = {"name": str(author)}

    content = _first_text(message, ("content", "Content", "text", "Text"))
    if not content:
        content = _render_content_parts(message.get("contents") or message.get("Contents"))

    attachments = message.get("attachments") or message.get("Attachments") or []
    embeds = message.get("embeds") or message.get("Embeds") or []

    author_name = _first_text(author, ("name", "username", "Name", "Username")) or "unknown"
    display_name = (
        _first_text(author, ("nickname", "displayName", "globalName", "Nickname", "DisplayName"))
        or author_name
    )

    return NormalizedMessage(
        source_file=source_path.name,
        source_message_id=_first_text(message, ("id", "Id", "messageId", "MessageId")),
        channel_id=_first_text(channel, ("id", "Id")),
        channel_name=_first_text(channel, ("name", "Name")) or _first_text(message, ("channelName", "ChannelName")),
        timestamp=_first_text(message, ("timestamp", "Timestamp", "createdAt", "CreatedAt")),
        author_id=_first_text(author, ("id", "Id")),
        author_name=author_name,
        author_display_name=display_name,
        is_bot=bool(author.get("isBot") or author.get("bot") or author.get("IsBot")),
        content=str(content).strip(),
        attachment_count=len(attachments) if isinstance(attachments, list) else 0,
        embed_count=len(embeds) if isinstance(embeds, list) else 0,
    )


def _first_text(mapping: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = mapping.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _render_content_parts(parts: Any) -> str:
    if not isinstance(parts, list):
        return ""
    rendered: list[str] = []
    for part in parts:
        if isinstance(part, str):
            rendered.append(part)
        elif isinstance(part, dict):
            rendered.append(str(part.get("text") or part.get("content") or ""))
    return " ".join(item for item in rendered if item).strip()

