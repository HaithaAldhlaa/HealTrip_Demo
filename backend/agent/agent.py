"""The single HealTrip AI Agent.

One agent, one loop, native tool calling:

    messages -> LLM -> (tool call | final answer)
                          tool call -> search_providers() -> verified JSON
                          -> back to the LLM with the tool result

The agent never sees the raw JSON files and can only talk about providers
through tool results.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from llm_client import chat_completion
from safety import CLARIFY_DIRECTIVE_AR, CLARIFY_DIRECTIVE_EN, URGENT_DIRECTIVE_AR, URGENT_DIRECTIVE_EN
from settings import settings
from tools.search_providers import (
    LIST_PROVIDER_FILTERS_TOOL,
    SEARCH_PROVIDERS_TOOL,
    MockDataError,
    ProviderRepository,
    get_repository,
)

TOOLS = [SEARCH_PROVIDERS_TOOL, LIST_PROVIDER_FILTERS_TOOL]

MAX_TOOL_ROUNDS = max(1, settings.max_tool_rounds)


class ToolError(RuntimeError):
    """A tool could not be executed (bad arguments or bad mock data)."""


@dataclass
class AgentResult:
    reply: str
    urgent: bool
    grounded: bool
    providers: list[dict[str, Any]] = field(default_factory=list)
    tools_used: list[dict[str, Any]] = field(default_factory=list)


def build_system_prompt(language: str, urgent: bool, needs_clarification: bool) -> str:
    prompt = (
        "You are HealTrip's patient decision-support assistant. You help a patient "
        "decide what kind of care to seek next. You are not a doctor and you never "
        "diagnose.\n\n"
        "Hard rules:\n"
        "1. Provider facts (doctor names, hospital names, specialties, addresses, "
        "languages, emergency availability, which hospital a doctor works at) may "
        "ONLY come from a search_providers tool result. Never use your own "
        "knowledge, never guess, never invent or rename a provider, and never "
        "describe a provider the tool did not return in this conversation. Copy "
        "names exactly as written in the tool result, and show only one name "
        "variant per provider (`name` for English replies, `name_ar` for Arabic "
        "replies).\n"
        "2. If the tool returns no match, say plainly that no matching provider "
        "exists in the available demo provider data. Do not suggest alternatives "
        "from memory.\n"
        "3. Call list_provider_filters when you are unsure of the exact specialty / "
        "city values, and always call search_providers when the patient asks about a "
        "doctor, hospital, clinic or where to go.\n"
        "4. Every match you receive is also rendered to the patient as a verified "
        "card, so keep your written answer consistent with the matches you were "
        "given: list them all, or explain why you are highlighting only some.\n"
        "5. Ask ONE short clarifying question when the request is ambiguous or when a "
        "symptom is reported without enough context.\n"
        "6. Never state or imply a diagnosis and never claim certainty. Mention "
        "possibilities and recommend evaluation by a qualified professional.\n"
        "7. Be brief and practical (about 120 words or less).\n"
        f"8. Reply in {'Arabic' if language == 'ar' else 'English'} — mirror the "
        "language the patient used.\n"
        "9. The provider data is fictional demo data and this is decision support "
        "only; it does not replace a clinician or emergency services."
    )
    if urgent:
        prompt += "\n\n" + (URGENT_DIRECTIVE_AR if language == "ar" else URGENT_DIRECTIVE_EN)
    elif needs_clarification:
        prompt += "\n\n" + (CLARIFY_DIRECTIVE_AR if language == "ar" else CLARIFY_DIRECTIVE_EN)
    return prompt


def run_tool(name: str, arguments: dict[str, Any], repo: ProviderRepository) -> dict[str, Any]:
    """Execute one tool call and return the JSON payload handed back to the LLM."""
    if name == "search_providers":
        provider_type = str(arguments.get("provider_type", "")).strip().lower()
        if provider_type not in {"doctor", "hospital"}:
            raise ToolError("provider_type must be 'doctor' or 'hospital'")
        results = repo.search(
            provider_type=provider_type,  # type: ignore[arg-type]
            specialty=arguments.get("specialty"),
            city=arguments.get("city"),
            language=arguments.get("language"),
        )
        return {
            "provider_type": provider_type,
            "filters": {
                "specialty": arguments.get("specialty"),
                "city": arguments.get("city"),
                "language": arguments.get("language"),
            },
            "match_count": len(results),
            "matches": results,
            "note": "Every match below exists in the demo provider database. Do not add providers.",
        }
    if name == "list_provider_filters":
        return {"available_filters": repo.facets()}
    raise ToolError(f"unknown tool: {name}")


async def run_agent(
    history: list[dict[str, str]],
    message: str,
    language: str,
    urgent: bool,
    needs_clarification: bool,
    repo: ProviderRepository | None = None,
) -> AgentResult:
    """Run the single agent loop until it produces a final text answer."""
    repo = repo or get_repository()

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": build_system_prompt(language, urgent, needs_clarification)},
        *history,
        {"role": "user", "content": message},
    ]

    tools_used: list[dict[str, Any]] = []
    providers: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    grounded = False

    for _ in range(MAX_TOOL_ROUNDS):
        reply_message = await chat_completion(messages, TOOLS)
        tool_calls = reply_message.get("tool_calls") or []

        if not tool_calls:
            content = (reply_message.get("content") or "").strip()
            if not content:
                raise ToolError("empty assistant response")
            return AgentResult(
                reply=content,
                urgent=urgent,
                grounded=grounded,
                providers=providers,
                tools_used=tools_used,
            )

        messages.append(reply_message)
        for call in tool_calls:
            function = call.get("function", {})
            name = function.get("name", "")
            raw_arguments = function.get("arguments") or "{}"
            try:
                arguments = _parse_arguments(raw_arguments)
                payload = run_tool(name, arguments, repo)
            except (ToolError, ValueError, MockDataError) as exc:
                payload = {"error": str(exc), "match_count": 0, "matches": []}

            matches = payload.get("matches", []) or []
            tools_used.append({"name": name, "arguments": arguments, "result_count": len(matches)})
            if name == "search_providers" and matches:
                grounded = True
                for match in matches:
                    key = (match["type"], match["id"])
                    if key not in seen:
                        seen.add(key)
                        providers.append(match)

            messages.append(
                {"role": "tool", "tool_call_id": call.get("id", "call"), "content": _to_json(payload)}
            )

    # Round cap reached: ask once more, without tools, so the patient still gets
    # an answer built on whatever the agent already verified.
    final = await chat_completion(messages, [])
    content = (final.get("content") or "").strip()
    if not content:
        raise ToolError("tool_round_limit_reached")
    return AgentResult(
        reply=content,
        urgent=urgent,
        grounded=grounded,
        providers=providers,
        tools_used=tools_used,
    )


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    parsed = json.loads(raw or "{}")
    if not isinstance(parsed, dict):
        raise ToolError("tool arguments must be a JSON object")
    return parsed


def _to_json(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False)