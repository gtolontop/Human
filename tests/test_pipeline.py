from __future__ import annotations

from pathlib import Path

from src.anonymizer import anonymize_rows
from src.cleaned_conversations import CleanedConversationConfig, build_cleaned_conversations
from src.dataset_builder import DatasetConfig, build_training_examples
from src.discord_export import parse_discord_chat_exporter
from src.message_splitter import parse_model_messages
from src.style_profile import build_style_profile


def test_discord_export_to_dataset_pipeline() -> None:
    payload = {
        "channel": {"id": "111111111111111111", "name": "general"},
        "messages": [
            {
                "id": "222222222222222222",
                "timestamp": "2026-01-01T10:00:00Z",
                "author": {"id": "333333333333333333", "name": "Friend"},
                "content": "Salut Alice, tu viens ? mail me@example.com",
            },
            {
                "id": "222222222222222223",
                "timestamp": "2026-01-01T10:00:03Z",
                "author": {"id": "444444444444444444", "name": "Alice"},
                "content": "ouais j'arrive",
            },
            {
                "id": "222222222222222224",
                "timestamp": "2026-01-01T10:00:05Z",
                "author": {"id": "444444444444444444", "name": "Alice"},
                "content": "2 sec",
            },
        ],
    }

    rows = parse_discord_chat_exporter(payload, Path("fake.json"))
    anonymized, summary = anonymize_rows(rows, target_author="Alice")
    examples = build_training_examples(anonymized, DatasetConfig())
    profile = build_style_profile(anonymized)

    assert len(rows) == 3
    assert summary["rows"] == 3
    assert "<EMAIL_" in anonymized[0]["content"]
    assert "Alice" not in anonymized[0]["content"]
    assert anonymized[1]["author"] == "<TARGET_USER>"
    assert examples[0]["output"]["messages"] == ["ouais j'arrive", "2 sec"]
    assert profile["target_message_count"] == 2


def test_parse_model_messages_prefers_json() -> None:
    raw = '```json\n{"messages":["salut","ça va ?"]}\n```'
    assert parse_model_messages(raw) == ["salut", "ça va ?"]


def test_build_cleaned_conversations_groups_target_bursts() -> None:
    payload = {
        "channel": {"id": "111111111111111111", "name": "general"},
        "messages": [
            {
                "id": "222222222222222222",
                "timestamp": "2026-01-01T10:00:00+00:00",
                "author": {"id": "333333333333333333", "name": "Friend"},
                "content": "Alice tu check https://private.example ? contact a@example.com",
            },
            {
                "id": "222222222222222223",
                "timestamp": "2026-01-01T10:00:30+00:00",
                "author": {"id": "444444444444444444", "name": "Alice"},
                "content": "ouais j'arrive",
            },
            {
                "id": "222222222222222224",
                "timestamp": "2026-01-01T10:01:00+00:00",
                "author": {"id": "444444444444444444", "name": "Alice"},
                "content": "2 sec jsp",
            },
        ],
    }

    rows = parse_discord_chat_exporter(payload, Path("fake.json"))
    conversations = build_cleaned_conversations(
        rows,
        CleanedConversationConfig(target_user_id="444444444444444444", reply_burst_minutes=5),
    )

    assert len(conversations) == 1
    assert conversations[0]["context"] == [
        {"speaker": "PERSON_A", "text": "ME tu check <URL> ? contact <EMAIL>"}
    ]
    assert conversations[0]["target_messages"] == ["ouais j'arrive", "2 sec jsp"]
    assert conversations[0]["meta"]["source"] == "discord"
    assert conversations[0]["meta"]["timestamps"] == [
        "2026-01-01T10:00:30+00:00",
        "2026-01-01T10:01:00+00:00",
    ]
