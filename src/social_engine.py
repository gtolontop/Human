from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DIRECT_PATTERNS = re.compile(r"\b(bot|human|toi|tu|t'es|tes|stp|svp|répond|repond)\b", re.I)
GREETING_RE = re.compile(r"\b(salut|yo|cc|coucou|wsh|hey|hello)\b", re.I)
QUESTION_RE = re.compile(r"\?|^(pq|pk|pourquoi|tfq|tu fais quoi|quoi|qui|comment|quand)\b", re.I)
REQUEST_RE = re.compile(r"\b(peux|peut|fais|fait|donne|envoie|aide|check|regarde|dis|explique)\b", re.I)
VENTING_RE = re.compile(r"\b(jpp|marre|saoule|triste|mal|énerv|enerve|stress|fatigu|nul|ça me gonfle)\b", re.I)
JOKE_RE = re.compile(r"\b(mdr|ptdr|xptdr|lol|haha)\b", re.I)
INSULT_RE = re.compile(r"\b(con|fdp|tg|ntm|pute|sale|débile|debile|idiot)\b", re.I)
AFFECTION_RE = re.compile(r"\b<3|❤️|merci|tkt|love|bisous|bg|frero|frère|mon reuf\b", re.I)
URGENT_RE = re.compile(r"\b(vite|urgent|maintenant|help|stp|svp|go|viens)\b", re.I)


@dataclass
class EmotionalState:
    energy: float = 0.62
    attention: float = 0.7
    stress: float = 0.18
    patience: float = 0.72
    playfulness: float = 0.35
    affection: float = 0.3
    irritation: float = 0.08
    curiosity: float = 0.45


@dataclass
class PersonMemory:
    user_id: str
    display_name: str | None = None
    relationship: str = "unknown"
    familiarity: float = 0.0
    trust: float = 0.15
    warmth: float = 0.25
    irritation: float = 0.0
    messages_seen: int = 0
    direct_messages: int = 0
    last_interaction_at: str | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class ConversationMemory:
    conversation_id: str
    messages_seen: int = 0
    last_messages: list[dict[str, str]] = field(default_factory=list)
    last_interaction_at: str | None = None


@dataclass
class SocialState:
    emotion: EmotionalState = field(default_factory=EmotionalState)
    people: dict[str, PersonMemory] = field(default_factory=dict)
    conversations: dict[str, ConversationMemory] = field(default_factory=dict)
    updated_at: str | None = None


@dataclass(frozen=True)
class MessageAnalysis:
    addressing_bot: bool
    intent: str
    tone: str
    urgency: float
    reply_expected: bool


@dataclass(frozen=True)
class ReplyDecision:
    should_reply: bool
    delay_seconds: float
    reply_style: str
    max_messages: int
    emotional_color: str
    reason: str


def load_social_state(path: Path) -> SocialState:
    if not path.exists():
        return SocialState()
    payload = json.loads(path.read_text(encoding="utf-8"))
    emotion = EmotionalState(**payload.get("emotion", {}))
    people = {
        key: PersonMemory(**value)
        for key, value in payload.get("people", {}).items()
        if isinstance(value, dict)
    }
    conversations = {
        key: ConversationMemory(**value)
        for key, value in payload.get("conversations", {}).items()
        if isinstance(value, dict)
    }
    return SocialState(
        emotion=emotion,
        people=people,
        conversations=conversations,
        updated_at=payload.get("updated_at"),
    )


def save_social_state(path: Path, state: SocialState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def analyze_message(
    text: str,
    *,
    bot_names: list[str],
    is_dm: bool,
    mentioned: bool,
    user_id: str,
    state: SocialState,
) -> MessageAnalysis:
    lowered = text.casefold()
    direct_name = any(name.casefold() in lowered for name in bot_names if name)
    addressing = is_dm or mentioned or direct_name or bool(DIRECT_PATTERNS.search(text))
    intent = detect_intent(text)
    tone = detect_tone(text)
    urgency = detect_urgency(text)
    person = state.people.get(user_id)
    if person and person.relationship in {"close_friend", "trusted"} and intent in {"greeting", "smalltalk"}:
        addressing = True
    reply_expected = addressing or intent in {"question", "request", "venting", "conflict"}
    return MessageAnalysis(
        addressing_bot=addressing,
        intent=intent,
        tone=tone,
        urgency=urgency,
        reply_expected=reply_expected,
    )


def decide_reply(analysis: MessageAnalysis, state: SocialState, person: PersonMemory) -> ReplyDecision:
    emotion = state.emotion
    should_reply = analysis.reply_expected
    reason = "reply_expected" if should_reply else "observe_only"
    if analysis.tone == "hostile" and emotion.patience < 0.25:
        should_reply = False
        reason = "low_patience_hostile"
    if not analysis.addressing_bot and analysis.intent not in {"question", "request"}:
        should_reply = False
        reason = "not_addressed"

    delay = 0.8 + (1.0 - emotion.energy) * 4.0 + emotion.stress * 2.0
    if analysis.urgency > 0.65:
        delay *= 0.35
    if person.relationship in {"close_friend", "trusted"}:
        delay *= 0.65
    delay = round(max(0.2, min(delay, 12.0)), 2)

    style = "short_burst"
    max_messages = 3
    if analysis.intent == "venting":
        style = "soft_supportive"
        max_messages = 4
    elif analysis.tone == "hostile":
        style = "dry_boundary"
        max_messages = 2
    elif emotion.energy < 0.25:
        style = "low_energy"
        max_messages = 2
    elif emotion.playfulness > 0.7:
        style = "playful"
        max_messages = 4

    return ReplyDecision(
        should_reply=should_reply,
        delay_seconds=delay,
        reply_style=style,
        max_messages=max_messages,
        emotional_color=emotional_color(emotion),
        reason=reason,
    )


def update_social_state(
    state: SocialState,
    *,
    user_id: str,
    display_name: str | None,
    conversation_id: str,
    text: str,
    analysis: MessageAnalysis,
    replied: bool,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(timezone.utc)
    now_text = now.isoformat()
    person = state.people.setdefault(user_id, PersonMemory(user_id=user_id, display_name=display_name))
    conversation = state.conversations.setdefault(conversation_id, ConversationMemory(conversation_id=conversation_id))

    person.display_name = display_name or person.display_name
    person.messages_seen += 1
    person.last_interaction_at = now_text
    if analysis.addressing_bot:
        person.direct_messages += 1
    person.familiarity = clamp(person.familiarity + 0.02 + (0.03 if replied else 0.0))
    person.trust = clamp(person.trust + (0.015 if analysis.tone in {"friendly", "affectionate"} else 0.0))
    person.warmth = clamp(person.warmth + (0.03 if analysis.tone in {"friendly", "affectionate"} else -0.01 if analysis.tone == "hostile" else 0.0))
    person.irritation = clamp(person.irritation + (0.08 if analysis.tone == "hostile" else -0.02))
    if person.familiarity > 0.75 and person.warmth > 0.55:
        person.relationship = "close_friend"
    elif person.familiarity > 0.35:
        person.relationship = "friend"
    elif person.irritation > 0.55:
        person.relationship = "annoying"

    conversation.messages_seen += 1
    conversation.last_interaction_at = now_text
    conversation.last_messages.append({"speaker": display_name or user_id, "text": text[:240]})
    del conversation.last_messages[:-30]

    update_emotion(state.emotion, analysis)
    state.updated_at = now_text


def update_emotion(emotion: EmotionalState, analysis: MessageAnalysis) -> None:
    emotion.attention = clamp(emotion.attention + (0.08 if analysis.addressing_bot else -0.03))
    emotion.curiosity = clamp(emotion.curiosity + (0.08 if analysis.intent in {"question", "request"} else -0.02))
    emotion.stress = clamp(emotion.stress + (0.08 if analysis.urgency > 0.6 else -0.015))
    emotion.irritation = clamp(emotion.irritation + (0.12 if analysis.tone == "hostile" else -0.025))
    emotion.patience = clamp(emotion.patience - (0.1 if analysis.tone == "hostile" else 0.015 if analysis.intent == "request" else -0.01))
    emotion.playfulness = clamp(emotion.playfulness + (0.08 if analysis.intent == "joke" else -0.02))
    emotion.affection = clamp(emotion.affection + (0.08 if analysis.tone == "affectionate" else -0.01))
    emotion.energy = clamp(emotion.energy - 0.01 + (0.03 if analysis.intent == "joke" else 0.0))


def social_prompt_block(analysis: MessageAnalysis, decision: ReplyDecision, person: PersonMemory, state: SocialState) -> str:
    payload = {
        "emotion": rounded_dict(asdict(state.emotion)),
        "person": {
            "relationship": person.relationship,
            "familiarity": round(person.familiarity, 3),
            "trust": round(person.trust, 3),
            "warmth": round(person.warmth, 3),
            "irritation": round(person.irritation, 3),
        },
        "analysis": asdict(analysis),
        "decision": asdict(decision),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def detect_intent(text: str) -> str:
    stripped = text.strip().casefold()
    if INSULT_RE.search(text):
        return "conflict"
    if VENTING_RE.search(text):
        return "venting"
    if REQUEST_RE.search(text):
        return "request"
    if QUESTION_RE.search(text):
        return "question"
    if JOKE_RE.search(text):
        return "joke"
    if GREETING_RE.search(text):
        return "greeting"
    if stripped in {"ok", "ah ok", "oe", "ouais", "non", "nn"}:
        return "ack"
    return "smalltalk"


def detect_tone(text: str) -> str:
    if INSULT_RE.search(text):
        return "hostile"
    if AFFECTION_RE.search(text):
        return "affectionate"
    if JOKE_RE.search(text) or ":)" in text:
        return "playful"
    if "!" in text or text.isupper():
        return "energetic"
    return "friendly"


def detect_urgency(text: str) -> float:
    urgency = 0.15
    if URGENT_RE.search(text):
        urgency += 0.55
    if "??" in text or "!!" in text:
        urgency += 0.2
    return clamp(urgency)


def emotional_color(emotion: EmotionalState) -> str:
    if emotion.irritation > 0.55:
        return "irritated_dry"
    if emotion.energy < 0.3:
        return "tired_low_energy"
    if emotion.playfulness > 0.65:
        return "playful"
    if emotion.affection > 0.6:
        return "warm"
    if emotion.stress > 0.55:
        return "stressed_fast"
    return "neutral_present"


def clamp(value: float) -> float:
    if math.isnan(value):
        return 0.0
    return max(0.0, min(1.0, value))


def rounded_dict(payload: dict[str, float]) -> dict[str, float]:
    return {key: round(float(value), 3) for key, value in payload.items()}
