from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DatasetConfig:
    max_context_messages: int = 12
    max_response_messages: int = 6
    min_context_messages: int = 1
    include_target_in_context: bool = True


def build_training_examples(rows: list[dict[str, Any]], config: DatasetConfig) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    index = 0
    while index < len(rows):
        row = rows[index]
        if not row.get("is_target") or _is_unusable(row):
            index += 1
            continue

        burst: list[dict[str, Any]] = []
        while index < len(rows) and rows[index].get("is_target") and not _is_unusable(rows[index]):
            burst.append(rows[index])
            index += 1
            if len(burst) >= config.max_response_messages:
                break

        context_rows = _context_before(rows, start_index=index - len(burst), config=config)
        if len(context_rows) < config.min_context_messages:
            continue

        examples.append(
            {
                "id": f"example_{len(examples) + 1:06d}",
                "input": {
                    "context": [
                        {"author": item.get("author"), "content": item.get("content", "")}
                        for item in context_rows
                    ],
                    "instruction": "Réponds comme le compte cible. Retourne uniquement un JSON {\"messages\": [..]}.",
                },
                "output": {"messages": [str(item.get("content") or "") for item in burst]},
                "meta": {
                    "target_message_count": len(burst),
                    "last_timestamp": burst[-1].get("timestamp"),
                },
            }
        )

    return examples


def _context_before(rows: list[dict[str, Any]], *, start_index: int, config: DatasetConfig) -> list[dict[str, Any]]:
    context: list[dict[str, Any]] = []
    cursor = start_index - 1
    while cursor >= 0 and len(context) < config.max_context_messages:
        row = rows[cursor]
        cursor -= 1
        if _is_unusable(row):
            continue
        if row.get("is_target") and not config.include_target_in_context:
            continue
        context.append(row)
    context.reverse()
    return context


def _is_unusable(row: dict[str, Any]) -> bool:
    return bool(row.get("is_bot")) or not str(row.get("content") or "").strip()

