from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .data_io import iter_jsonl, read_json
from .output_parser import messages_json


SYSTEM_PROMPT = """Tu es un assistant qui répond dans le style d'écriture du compte cible.
Contraintes strictes:
- Retourne uniquement un JSON valide de forme {"messages":["msg1","msg2"]}.
- Sépare naturellement la réponse en plusieurs petits messages quand ça colle au style.
- Français natif, anglais occasionnel seulement si naturel dans le contexte.
- Garde les fautes, abréviations, rythme et syntaxe du style cible.
- N'invente pas d'informations privées et ne désanonymise personne.
- Ne copie pas de longs exemples: imite seulement le style.
- N'ajoute jamais d'explication, de markdown ou de raisonnement hors JSON.
"""


def load_fewshot_examples(path: Path | None, *, limit: int) -> list[dict[str, Any]]:
    if not path or limit <= 0 or not path.exists():
        return []
    if path.suffix.lower() == ".jsonl":
        rows = list(iter_jsonl(path))
    else:
        payload = read_json(path)
        rows = payload if isinstance(payload, list) else payload.get("examples", [])
    return [_normalize_example(row) for row in rows[:limit] if isinstance(row, dict)]


def load_history(path: Path | None) -> list[str]:
    if not path:
        return []
    if path.suffix.lower() == ".jsonl":
        lines = []
        for row in iter_jsonl(path):
            speaker = row.get("speaker") or row.get("role") or "user"
            text = row.get("text") or row.get("content") or row.get("message")
            if text:
                lines.append(f"{speaker}: {text}")
        return lines
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_chat_messages(
    *,
    user_message: str,
    context: list[str],
    style_profile: dict[str, Any] | None,
    fewshot_examples: list[dict[str, Any]],
    thinking: bool,
) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": _system_prompt(style_profile, thinking=thinking)}]
    for example in fewshot_examples:
        messages.append({"role": "user", "content": _format_user_turn(example["context"], "Réponds à ce contexte.")})
        messages.append({"role": "assistant", "content": messages_json(example["target_messages"])})
    messages.append({"role": "user", "content": _format_user_turn(context, user_message)})
    return messages


def _system_prompt(style_profile: dict[str, Any] | None, *, thinking: bool) -> str:
    compact_profile = json.dumps(style_profile or {}, ensure_ascii=False, separators=(",", ":"))
    thinking_line = (
        "Tu peux raisonner brièvement en interne, mais la sortie visible reste seulement le JSON final."
        if thinking
        else "Ne produis aucune trace de raisonnement visible; seulement le JSON final."
    )
    return f"{SYSTEM_PROMPT}\nProfil de style agrégé anonymisé:\n{compact_profile}\n{thinking_line}"


def _format_user_turn(context: list[str], user_message: str) -> str:
    recent = "\n".join(context[-30:]) if context else "(aucun contexte)"
    return (
        "Historique récent:\n"
        f"{recent}\n\n"
        "Dernier message utilisateur:\n"
        f"{user_message}\n\n"
        'Réponds uniquement avec {"messages":["..."]}.'
    )


def _normalize_example(row: dict[str, Any]) -> dict[str, Any]:
    if "target_messages" in row:
        context = row.get("context") or []
        return {
            "context": [_context_line(item) for item in context if _context_line(item)],
            "target_messages": [str(item) for item in row.get("target_messages", []) if str(item).strip()],
        }

    output = row.get("output") if isinstance(row.get("output"), dict) else {}
    input_payload = row.get("input") if isinstance(row.get("input"), dict) else {}
    return {
        "context": [_context_line(item) for item in input_payload.get("context", []) if _context_line(item)],
        "target_messages": [str(item) for item in output.get("messages", []) if str(item).strip()],
    }


def _context_line(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if not isinstance(item, dict):
        return ""
    speaker = item.get("speaker") or item.get("author") or item.get("role") or "user"
    text = item.get("text") or item.get("content") or item.get("message") or ""
    text = str(text).strip()
    if not text:
        return ""
    return f"{speaker}: {text}"
