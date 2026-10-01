"""FastAPI backend for the HealTrip AI Patient Decision Assistant prototype.

One public endpoint (POST /api/chat) plus a health check. All LLM interaction,
tool calling and mock-data search happen here so API keys stay server-side.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from agent.agent import ToolError, run_agent
from guard import enforce_grounding
from llm_client import LLMError
from safety import detect_language, is_emergency, mentions_symptom
from schemas import ChatRequest, ChatResponse
from settings import settings
from tools.search_providers import MockDataError, get_repository

logger = logging.getLogger("healtrip")

app = FastAPI(title="HealTrip AI Patient Decision Assistant (prototype)", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)

# User-facing, provider-agnostic error messages. Nothing internal leaks here.
ERRORS: dict[str, tuple[str, str]] = {
    "invalid_request": ("Please check your message and try again.", "يرجى مراجعة رسالتك والمحاولة مرة أخرى."),
    "empty_message": ("Please type a message first.", "يرجى كتابة رسالة أولاً."),
    "missing_api_key": (
        "The AI service is not configured yet. Please try again later.",
        "لم يتم إعداد خدمة الذكاء الاصطناعي بعد. يرجى المحاولة لاحقاً.",
    ),
    "llm_timeout": (
        "The AI service took too long to respond. Please try again.",
        "استغرقت خدمة الذكاء الاصطناعي وقتاً طويلاً للرد. يرجى المحاولة مرة أخرى.",
    ),
    "llm_unavailable": (
        "The AI service is temporarily unavailable. Please try again.",
        "خدمة الذكاء الاصطناعي غير متاحة مؤقتاً. يرجى المحاولة مرة أخرى.",
    ),
    "mock_data_error": (
        "The demo provider data is unavailable right now.",
        "بيانات مزوّدي الخدمة التوضيحية غير متاحة حالياً.",
    ),
    "internal_error": (
        "Something went wrong. Please try again.",
        "حدث خطأ ما. يرجى المحاولة مرة أخرى.",
    ),
}

URGENT_NOTICE = {
    "en": "If this may be an emergency, call your local emergency number or go to the nearest emergency department now.",
    "ar": "إذا كانت الحالة طارئة، فاتصل برقم الطوارئ المحلي أو توجّه إلى أقرب قسم طوارئ فوراً.",
}


def _error(status_code: int, code: str, language: str) -> JSONResponse:
    en, ar = ERRORS[code]
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": ar if language == "ar" else en}},
    )


@app.exception_handler(RequestValidationError)
async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Log the shape of the problem only - never the medical content.
    logger.warning("invalid request payload: %s", exc.errors()[0].get("type", "unknown"))
    return _error(422, "invalid_request", "en")


@app.exception_handler(StarletteHTTPException)
async def _http_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _error(exc.status_code, "internal_error", "en")


@app.exception_handler(Exception)
async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled error: %s", type(exc).__name__)
    return _error(500, "internal_error", "en")


@app.get("/health")
async def health() -> dict[str, Any]:
    """Liveness probe used by local setup and by the Vercel demo setup."""
    return {"status": "ok", "llm_configured": settings.has_api_key, "provider": settings.provider}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse | JSONResponse:
    language = request.language or detect_language(request.message)

    if not settings.has_api_key:
        return _error(503, "missing_api_key", language)

    urgent = is_emergency(request.message)
    needs_clarification = not urgent and mentions_symptom(request.message)
    history = [{"role": turn.role, "content": turn.content} for turn in request.history]

    try:
        repo = get_repository()  # raises MockDataError when the JSON files are broken
        result = await run_agent(
            history=history,
            message=request.message,
            language=language,
            urgent=urgent,
            needs_clarification=needs_clarification,
            repo=repo,
        )
    except MockDataError:
        logger.error("mock database is invalid")
        return _error(500, "mock_data_error", language)
    except LLMError as exc:
        logger.error("llm failure: %s", exc)
        code = "llm_timeout" if str(exc) == "llm_timeout" else "llm_unavailable"
        return _error(502 if code == "llm_unavailable" else 504, code, language)
    except ToolError as exc:
        logger.error("tool failure: %s", exc)
        return _error(500, "internal_error", language)

    reply, unverified = enforce_grounding(result.reply, repo, language)
    if unverified:
        logger.warning("rejected reply: %d unverified provider name(s)", len(unverified))

    return ChatResponse(
        reply=reply,
        language=language,
        urgent=urgent,
        grounded=result.grounded and not unverified,
        providers=result.providers if not unverified else [],
        tools_used=result.tools_used,
        safety_notice=URGENT_NOTICE[language] if urgent else None,
    )