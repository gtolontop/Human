from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


DEFAULT_ABBREVIATIONS: dict[str, str] = {
    "cdq": "c'est quoi",
    "c quoi": "c'est quoi",
    "cqui": "c'est qui",
    "cv": "ça va",
    "jpp": "j'en peux plus",
    "jsp": "je sais pas",
    "mdr": "rire / amusé",
    "oe": "ouais",
    "oue": "ouais",
    "pk": "pourquoi",
    "pq": "pourquoi",
    "ptdr": "rire fort",
    "stp": "s'il te plait",
    "tfq": "tu fais quoi",
    "tkt": "t'inquiète",
    "wsh": "salut / interpellation",
}

FRENCH_HINTS = {
    "alors",
    "avec",
    "bah",
    "bien",
    "cest",
    "c'est",
    "dans",
    "donc",
    "genre",
    "grave",
    "j'ai",
    "jsp",
    "lourd",
    "ma",
    "mais",
    "mdr",
    "moi",
    "non",
    "ouais",
    "parce",
    "pourquoi",
    "quoi",
    "salut",
    "toi",
    "yo",
}
ENGLISH_HINTS = {
    "about",
    "because",
    "boy",
    "bro",
    "can",
    "cool",
    "fine",
    "good",
    "hello",
    "hey",
    "how",
    "like",
    "lol",
    "maybe",
    "what",
    "when",
    "why",
    "yeah",
    "yo",
    "you",
}
QUESTION_PREFIXES = ("qui", "quoi", "quand", "comment", "pourquoi", "pq", "pk", "tfq", "what", "why", "how", "when")
WORD_RE = re.compile(r"[A-Za-zÀ-ÿ0-9_']+")


def load_abbreviations(path: Path | None) -> dict[str, str]:
    abbreviations = dict(DEFAULT_ABBREVIATIONS)
    if not path or not path.exists():
        return abbreviations
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return abbreviations
    custom = payload.get("abbreviations") if isinstance(payload, dict) else payload
    if not isinstance(custom, dict):
        return abbreviations
    for key, value in custom.items():
        key_text = str(key).casefold().strip()
        value_text = str(value).strip()
        if key_text and value_text:
            abbreviations[key_text] = value_text
    return abbreviations


def build_conversation_hints(user_message: str, history: list[str], abbreviations: dict[str, str]) -> str:
    language = detect_language("\n".join([*history[-6:], user_message]))
    detected = detect_abbreviations(user_message, abbreviations)
    intent = detect_intent(user_message, detected)
    hints = [
        f"language={language}",
        f"intent={intent}",
        "anti_echo=true",
    ]
    if detected:
        rendered = ", ".join(f"{abbr}={meaning}" for abbr, meaning in detected.items())
        hints.append(f"abbreviations={rendered}")
    if looks_like_unknown_slang(user_message, abbreviations):
        hints.append(
            "unknown_slang=Le dernier message ressemble a un slang/typo pas compris; "
            "ne le copie pas, demande une clarification tres courte ou reponds au ton."
        )
    if intent == "activity_question":
        hints.append("reply_rule=Dire ce que ME fait ou un etat actuel plausible, pas repeter la question.")
    elif intent == "reason_question":
        hints.append("reply_rule=Donner une cause courte si possible; si contexte insuffisant, le dire naturellement.")
    elif intent == "definition_question":
        hints.append("reply_rule=Expliquer ce que c'est si le contexte suffit; sinon demander 'c quoi ca' tres court.")
    elif intent == "status_question":
        hints.append("reply_rule=Repondre comme humain a 'ca va', puis petite relance si naturel.")
    elif intent == "greeting":
        hints.append("reply_rule=Salutation courte, pas de long bloc.")
    elif intent == "wait_ack":
        hints.append("reply_rule=Accuser reception tres court, pas relancer par une salutation.")
    elif intent == "help_request":
        hints.append("reply_rule=Accepter d'aider ou demander le detail si besoin, sans long pave.")
    elif intent == "later_help_request":
        hints.append("reply_rule=Confirmer que ME checkera plus tard, tres court.")
    elif intent == "advice_request":
        hints.append("reply_rule=Proposer une formulation courte ou une idee de reponse, pas parler d'un sujet random.")
    elif intent == "invite_request":
        hints.append("reply_rule=Repondre oui/non/plus tard clairement, pas esquiver.")
    elif intent == "emotion_check":
        hints.append("reply_rule=Repondre a l'etat emotionnel simplement, pas attaquer USER.")
    elif language == "en":
        hints.append("reply_rule=Repondre en anglais naturel si USER parle anglais.")
    elif language == "mixed":
        hints.append("reply_rule=Melanger francais/anglais legerement seulement si le contexte le fait.")
    return "\n".join(hints)


def detect_abbreviations(text: str, abbreviations: dict[str, str]) -> dict[str, str]:
    normalized = _normalize(text)
    words = set(_words(normalized))
    detected: dict[str, str] = {}
    for key, meaning in abbreviations.items():
        key_norm = _normalize(key)
        if " " in key_norm:
            if key_norm in normalized:
                detected[key] = meaning
        elif key_norm in words:
            detected[key] = meaning
    return detected


def detect_intent(text: str, detected_abbreviations: dict[str, str] | None = None) -> str:
    normalized = _normalize(text)
    compact = normalized.strip(" ?!.")
    detected_abbreviations = detected_abbreviations or {}
    words = set(_words(compact))
    if compact in {"salut", "slt", "yo", "hey", "hello", "cc", "coucou", "wsh"} or words & {
        "salut",
        "slt",
        "yo",
        "hey",
        "hello",
        "cc",
        "coucou",
        "wsh",
    }:
        return "greeting"
    if compact in {"att", "attends", "attend", "2 sec", "sec"}:
        return "wait_ack"
    if compact in {"ca va", "ça va", "cv", "sa va"} or compact.startswith(("ca va", "ça va")):
        return "status_question"
    if compact in {"how are you", "how r u", "hru"} or compact.startswith(("how are you", "how r u")):
        return "status_question"
    if "cdq" in detected_abbreviations or "c quoi" in detected_abbreviations or compact.startswith(("c quoi", "c'est quoi", "cest quoi")):
        return "definition_question"
    if "tfq" in detected_abbreviations or compact in {"tu fais quoi", "tfq", "tu fait quoi"}:
        return "activity_question"
    if compact.startswith(("what u doing", "what are you doing", "wyd")):
        return "activity_question"
    if "pq" in detected_abbreviations or "pk" in detected_abbreviations or compact.startswith(("pq", "pk", "pourquoi", "why")):
        return "reason_question"
    if any(word in compact for word in {"repondrais", "répondrais", "dire quoi", "formuler"}):
        return "advice_request"
    if ("apres" in words or "après" in words or "later" in words) and any(word in words for word in {"check", "aide", "aider", "help"}):
        return "later_help_request"
    if any(word in words for word in {"aide", "aider", "help", "check"}) or "aider" in compact or "help" in compact:
        return "help_request"
    if any(word in words for word in {"vocal", "call", "viens", "join", "go"}):
        return "invite_request"
    if any(word in words for word in {"fache", "enerve", "triste", "mad", "sad"}):
        return "emotion_check"
    if "?" in text or compact.startswith(QUESTION_PREFIXES):
        return "question"
    if any(word in compact.split() for word in ("mdr", "ptdr", "lol", "haha")):
        return "humor"
    return "chat"


def detect_language(text: str) -> str:
    words = set(_words(_normalize(text)))
    fr_score = len(words & FRENCH_HINTS)
    en_score = len(words & ENGLISH_HINTS)
    if fr_score and en_score:
        return "mixed"
    if en_score > fr_score:
        return "en"
    return "fr"


def looks_like_unknown_slang(text: str, abbreviations: dict[str, str]) -> bool:
    normalized = _normalize(text).strip(" ?!.")
    words = _words(normalized)
    if not words or len(words) > 4:
        return False
    known = set(abbreviations) | FRENCH_HINTS | ENGLISH_HINTS
    unknown_short = [word for word in words if len(word) <= 6 and word not in known and not word.isdigit()]
    if not unknown_short:
        return False
    return len(unknown_short) >= 1


def _normalize(text: str) -> str:
    return (
        text.casefold()
        .replace("’", "'")
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("à", "a")
        .replace("ç", "c")
    )


def _words(text: str) -> list[str]:
    return WORD_RE.findall(text)
