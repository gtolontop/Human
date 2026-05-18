from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from src.anonymizer import anonymize_rows
from src.cleaned_conversations import CleanedConversationConfig, build_cleaned_conversations
from src.conversation_features import (
    build_conversation_hints,
    detect_abbreviations,
    detect_intent,
    detect_language,
    load_abbreviations,
    looks_like_unknown_slang,
)
from src.cli import main as cli_main
from src.dataset_builder import DatasetConfig, build_training_examples
from src.discord_export import parse_discord_chat_exporter
from src.message_splitter import parse_model_messages
from src.output_parser import parse_strict_messages
from src.prompt_builder import load_fewshot_examples
from src.style_eval import build_blind_review, evaluate_predictions, parse_eval_rows
from src.social_engine import PersonMemory, SocialState, analyze_message, decide_reply, social_prompt_block, update_social_state
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


def test_output_parser_repairs_jsonish_messages() -> None:
    messages, was_strict = parse_strict_messages("messages: ['okok', 'je check']")
    assert messages == ["okok", "je check"]
    assert was_strict is False


def test_load_fewshot_examples_json() -> None:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "fewshot_examples.json"
        path.write_text(
            '{"examples":[{"context":[{"speaker":"PERSON_A","text":"tu viens ?"}],"target_messages":["ouais","2 sec"]}]}',
            encoding="utf-8",
        )
        examples = load_fewshot_examples(path, limit=2)
    assert examples == [{"context": ["PERSON_A: tu viens ?"], "target_messages": ["ouais", "2 sec"]}]


def test_cli_mock_prints_discord_lines() -> None:
    assert cli_main(["--mock", "--style-profile", "missing.json", "--fewshots", "missing.json", "tu peux check ?"]) == 0


def test_conversation_features_understand_short_slang() -> None:
    abbreviations = load_abbreviations(None)
    detected = detect_abbreviations("tfq ?", abbreviations)
    hints = build_conversation_hints("tfq ?", [], abbreviations)

    assert detected["tfq"] == "tu fais quoi"
    assert detect_intent("tfq ?", detected) == "activity_question"
    assert detect_intent("yo ma boy") == "greeting"
    assert detect_language("hey what are you doing bro") == "en"
    assert looks_like_unknown_slang("raoe lourd", abbreviations) is True
    assert "pas repeter la question" in hints


def test_style_eval_aggregates_and_blind_review() -> None:
    rows = [
        {
            "conversation_id": "case_1",
            "context": [{"speaker": "PERSON_A", "text": "tu viens ?"}],
            "target_messages": ["ouais 2 sec", "jsp"],
        }
    ]
    cases = parse_eval_rows(rows)
    report = evaluate_predictions(cases, {"case_1": ["ouais attends", "je check"]})
    blind = build_blind_review(cases, {"case_1": ["ouais attends", "je check"]})

    assert report["aggregate"]["cases"] == 1
    assert report["aggregate"]["generated_cases"] == 1
    assert "avg_lexical_jaccard" in report["aggregate"]["similarity"]
    assert blind[0]["review_id"]
    assert blind[0]["human_choice"] is None
    assert "answer_key" in blind[0]


def test_social_engine_observes_server_messages_and_replies_to_dm() -> None:
    state = SocialState()
    server_analysis = analyze_message(
        "vous avez vu ça mdr",
        bot_names=["human"],
        is_dm=False,
        mentioned=False,
        user_id="alice",
        state=state,
    )
    person = PersonMemory(user_id="alice", display_name="Alice")
    server_decision = decide_reply(server_analysis, state, person)

    dm_analysis = analyze_message(
        "salut ça va ?",
        bot_names=["human"],
        is_dm=True,
        mentioned=False,
        user_id="alice",
        state=state,
    )
    dm_decision = decide_reply(dm_analysis, state, person)
    update_social_state(
        state,
        user_id="alice",
        display_name="Alice",
        conversation_id="dm_alice",
        text="salut ça va ?",
        analysis=dm_analysis,
        replied=True,
    )

    assert server_analysis.addressing_bot is False
    assert server_decision.should_reply is False
    assert dm_analysis.addressing_bot is True
    assert dm_decision.should_reply is True
    assert state.people["alice"].messages_seen == 1
    assert "decision" in social_prompt_block(dm_analysis, dm_decision, state.people["alice"], state)
