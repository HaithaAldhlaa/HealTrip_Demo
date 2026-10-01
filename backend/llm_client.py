"""Thin OpenAI-compatible chat client.

The Agent only needs `POST {base_url}/chat/completions` with tool support, so
this module talks HTTP directly with httpx. Swapping provider (Groq,
DeepSeek, OpenRouter, a self-hosted vLLM...) is a `.env` change, not a code
change.
"""

from __future__ import annotations

from typing import Any

import httpx

from settings import settings


class LLMError(RuntimeError):
    """Any failure while talking to the LLM provider."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _payload(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": settings.model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 600,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    else:
        # Last-resort call: force a text answer from what is already known.
        payload["tool_choice"] = "none"
    return payload


async def chat_completion(
    messages: list[dict[str, Any]], tools: list[dict[str, Any]]
) -> dict[str, Any]:
    """Call the configured provider once and return the raw first choice."""
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
        # Some providers sit behind a WAF that rejects the default httpx agent.
        "User-Agent": "healtrip-ai-prototype/1.0",
    }
    try:
        async with httpx.AsyncClient(timeout=settings.timeout_seconds) as client:
            response = await client.post(
                settings.chat_completions_url, json=_payload(messages, tools), headers=headers
            )
    except httpx.TimeoutException as exc:
        raise LLMError("llm_timeout") from exc
    except httpx.HTTPError as exc:
        raise LLMError("llm_unreachable") from exc

    if response.status_code >= 400:
        # Provider detail is intentionally not forwarded to the browser.
        raise LLMError("llm_provider_error", status_code=response.status_code)

    try:
        body = response.json()
        return body["choices"][0]["message"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LLMError("llm_invalid_response") from exc