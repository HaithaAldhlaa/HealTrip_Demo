"""Pydantic request/response schemas for the single public endpoint."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

MAX_MESSAGE_LENGTH = 2000
MAX_HISTORY_MESSAGES = 12

Language = Literal["en", "ar"]
Role = Literal["user", "assistant"]


class ChatTurn(BaseModel):
    """A single prior conversation turn supplied by the client.

    There is no server-side conversation storage: the client keeps the short
    context so the Agent can ask and answer clarification questions.
    """

    role: Role
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    language: Language | None = None  # None/omitted => auto-detect from message
    history: list[ChatTurn] = Field(default_factory=list, max_length=MAX_HISTORY_MESSAGES)

    @field_validator("message", "history")
    @classmethod
    def strip_whitespace(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            for turn in value:
                turn.content = turn.content.strip()
        return value

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("empty_message")
        return value


class Provider(BaseModel):
    """Verified provider record. Every value here came from the mock JSON files."""

    type: Literal["doctor", "hospital"]
    id: str
    name: str
    name_ar: str | None = None
    city: str
    specialties: list[str] = Field(default_factory=list)
    hospital: str | None = None
    hospital_address: str | None = None
    emergency_available: bool | None = None
    languages: list[str] = Field(default_factory=list)


class ToolTrace(BaseModel):
    """Minimal trace so the demo can show *why* the Agent called a tool."""

    name: str
    arguments: dict[str, Any]
    result_count: int


class ChatResponse(BaseModel):
    reply: str
    language: Language
    urgent: bool = False
    grounded: bool = False  # True when the reply is built on verified tool data
    providers: list[Provider] = Field(default_factory=list)
    tools_used: list[ToolTrace] = Field(default_factory=list)
    safety_notice: str | None = None


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody