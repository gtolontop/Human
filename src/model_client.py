from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int = 120

    @classmethod
    def from_env(cls) -> "OpenAICompatibleConfig":
        return cls(
            base_url=os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1").rstrip("/"),
            api_key=os.getenv("OPENAI_API_KEY", "local-not-needed"),
            model=os.getenv("OPENAI_MODEL", "qwen3.6-27b"),
        )

    def with_overrides(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: int | None = None,
    ) -> "OpenAICompatibleConfig":
        return OpenAICompatibleConfig(
            base_url=(base_url or self.base_url).rstrip("/"),
            api_key=api_key or self.api_key,
            model=model or self.model,
            timeout_seconds=timeout_seconds or self.timeout_seconds,
        )


class ModelClientError(RuntimeError):
    pass


class OpenAICompatibleClient:
    def __init__(self, config: OpenAICompatibleConfig):
        self.config = config

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 512,
        response_format: bool = True,
    ) -> str:
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = {"type": "json_object"}
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.config.base_url}/chat/completions",
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ModelClientError(f"Model endpoint HTTP {exc.code}: {_short_error(body)}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise ModelClientError(f"Model endpoint timed out after {self.config.timeout_seconds}s") from exc
        except urllib.error.URLError as exc:
            raise ModelClientError(f"Cannot reach model endpoint: {exc.reason}") from exc

        try:
            payload = json.loads(raw)
            choice = payload["choices"][0]
            message = choice.get("message") or {}
            content = message.get("content")
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ModelClientError("Unexpected model response shape") from exc
        if not isinstance(content, str):
            raise ModelClientError("Model response did not contain text content")
        return content


def _short_error(text: str, limit: int = 240) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[:limit].rstrip() + "..."
