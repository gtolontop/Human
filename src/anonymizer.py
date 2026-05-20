from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s<>()]+|www\.[^\s<>()]+", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d .()/-]{7,}\d)(?!\w)")
DISCORD_ID_RE = re.compile(r"\b\d{17,20}\b")
MENTION_RE = re.compile(r"<@!?(\d{17,20})>|<@&(\d{17,20})>|<#(\d{17,20})>")
INVITE_RE = re.compile(r"(?:discord\.gg|discord(?:app)?\.com/invite)/[A-Za-z0-9-]+", re.IGNORECASE)
ADDRESS_RE = re.compile(
    r"\b\d{1,4}\s+(?:rue|avenue|av\.?|boulevard|bd\.?|chemin|impasse|place|route)\s+[A-Za-zÀ-ÿ0-9' -]{2,}",
    re.IGNORECASE,
)


@dataclass
class AnonymizationState:
    salt: str = ""
    mapping: dict[str, dict[str, str]] = field(
        default_factory=lambda: {
            "author": {},
            "mention": {},
            "email": {},
            "phone": {},
            "url": {},
            "discord_id": {},
            "location": {},
            "custom": {},
        }
    )
    counters: dict[str, int] = field(default_factory=dict)

    def placeholder(self, category: str, raw: str, prefix: str) -> str:
        raw = raw.strip()
        bucket = self.mapping.setdefault(category, {})
        if raw in bucket:
            return bucket[raw]
        self.counters[category] = self.counters.get(category, 0) + 1
        digest = hashlib.sha1(f"{self.salt}:{category}:{raw}".encode("utf-8")).hexdigest()[:6]
        value = f"<{prefix}_{self.counters[category]:04d}_{digest}>"
        bucket[raw] = value
        return value

    def to_public_summary(self) -> dict[str, int]:
        return {category: len(values) for category, values in sorted(self.mapping.items())}


def load_terms(path: Path | None) -> list[str]:
    if not path:
        return []
    terms: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            term = line.strip()
            if term and not term.startswith("#"):
                terms.append(term)
    return sorted(set(terms), key=len, reverse=True)


def anonymize_rows(
    rows: list[dict[str, Any]],
    *,
    target_author: str | None = None,
    target_author_id: str | None = None,
    custom_terms: list[str] | None = None,
    salt: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    state = AnonymizationState(salt=salt)
    terms = custom_terms or []
    target_author_norm = target_author.casefold() if target_author else None
    target_author_id_norm = target_author_id.strip() if target_author_id else None

    author_labels: list[str] = []
    target_flags: list[bool] = []
    visible_replacements: dict[str, str] = {}
    for row in rows:
        author_name = str(row.get("author_name") or "")
        display_name = str(row.get("author_display_name") or author_name)
        author_id = str(row.get("author_id") or "")
        is_target = _is_target(
            author_name=author_name,
            display_name=display_name,
            author_id=author_id,
            target_author=target_author_norm,
            target_author_id=target_author_id_norm,
        )
        raw_placeholder = state.placeholder("author", author_id or display_name or author_name, "USER")
        public_author = "<TARGET_USER>" if is_target else raw_placeholder
        author_labels.append(public_author)
        target_flags.append(is_target)
        for visible_name in {author_name, display_name} - {""}:
            if is_target or visible_name not in visible_replacements:
                visible_replacements[visible_name] = public_author

    result: list[dict[str, Any]] = []
    for row, public_author, is_target in zip(rows, author_labels, target_flags, strict=True):
        content = str(row.get("content") or "")

        for visible_name, replacement in sorted(visible_replacements.items(), key=lambda item: len(item[0]), reverse=True):
            content = _replace_literal(content, visible_name, replacement)

        content = anonymize_text(content, state=state, custom_terms=terms)
        result.append(
            {
                "timestamp": row.get("timestamp"),
                "channel": _safe_channel(row, state),
                "author": public_author,
                "is_target": is_target,
                "is_bot": bool(row.get("is_bot")),
                "content": content,
                "attachment_count": int(row.get("attachment_count") or 0),
                "embed_count": int(row.get("embed_count") or 0),
                "source": {
                    "file": row.get("source_file"),
                    "message_id": state.placeholder("discord_id", str(row.get("source_message_id")), "DISCORD_ID")
                    if row.get("source_message_id")
                    else None,
                },
            }
        )

    return result, {"replacements": state.to_public_summary(), "rows": len(result)}


def anonymize_text(text: str, *, state: AnonymizationState, custom_terms: list[str]) -> str:
    text = INVITE_RE.sub(lambda match: state.placeholder("url", match.group(0), "PRIVATE_URL"), text)
    text = MENTION_RE.sub(lambda match: state.placeholder("mention", match.group(0), "MENTION"), text)
    text = EMAIL_RE.sub(lambda match: state.placeholder("email", match.group(0), "EMAIL"), text)
    text = URL_RE.sub(lambda match: state.placeholder("url", match.group(0), "PRIVATE_URL"), text)
    text = PHONE_RE.sub(lambda match: state.placeholder("phone", match.group(0), "PHONE"), text)
    text = ADDRESS_RE.sub(lambda match: state.placeholder("location", match.group(0), "LOCATION"), text)
    text = DISCORD_ID_RE.sub(lambda match: state.placeholder("discord_id", match.group(0), "DISCORD_ID"), text)
    for term in custom_terms:
        text = _replace_literal(text, term, state.placeholder("custom", term, "PRIVATE_TERM"))
    return text


def write_private_mapping(path: Path, state_payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(state_payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _safe_channel(row: dict[str, Any], state: AnonymizationState) -> str | None:
    channel_id = row.get("channel_id")
    channel_name = row.get("channel_name")
    if channel_id:
        return state.placeholder("discord_id", str(channel_id), "CHANNEL")
    if channel_name:
        return state.placeholder("custom", str(channel_name), "CHANNEL")
    return None


def _is_target(
    *,
    author_name: str,
    display_name: str,
    author_id: str,
    target_author: str | None,
    target_author_id: str | None,
) -> bool:
    if target_author_id and author_id == target_author_id:
        return True
    if target_author:
        return target_author in {author_name.casefold(), display_name.casefold()}
    return False


def _replace_literal(text: str, needle: str, replacement: str) -> str:
    if not needle or len(needle) < 2:
        return text
    return re.sub(re.escape(needle), replacement, text, flags=re.IGNORECASE)
