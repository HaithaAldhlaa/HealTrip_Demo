"""Environment configuration for the HealTrip backend.

All secrets (LLM API keys) stay on the server and are read from environment
variables only. Nothing in this module is ever returned to the frontend.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"

# Prefer a root .env (shared with the frontend), fall back to backend/.env.
load_dotenv(REPO_ROOT / ".env")
load_dotenv(BACKEND_DIR / ".env")


def _provider_defaults(provider: str) -> tuple[str, str]:
    """Default base URL + model per provider (OpenAI-compatible chat API)."""
    defaults = {
        "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
        "groq": ("https://api.groq.com/openai/v1", "openai/gpt-oss-120b"),
        "deepseek": ("https://api.deepseek.com/v1", "deepseek-chat"),
        "openrouter": ("https://openrouter.ai/api/v1", "openai/gpt-4o-mini"),
    }
    return defaults.get(provider, ("https://api.openai.com/v1", "gpt-4o-mini"))


@dataclass(frozen=True)
class Settings:
    provider: str
    api_key: str | None
    model: str
    base_url: str
    timeout_seconds: float
    max_tool_rounds: int
    cors_origins: list[str]

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    @property
    def chat_completions_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"


def get_settings() -> Settings:
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    default_base_url, default_model = _provider_defaults(provider)
    origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    return Settings(
        provider=provider,
        api_key=os.getenv("LLM_API_KEY"),
        model=os.getenv("LLM_MODEL", default_model).strip() or default_model,
        base_url=os.getenv("LLM_BASE_URL", default_base_url).strip() or default_base_url,
        timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "45")),
        max_tool_rounds=int(os.getenv("MAX_TOOL_ROUNDS", "5")),
        cors_origins=[origin.strip() for origin in origins.split(",") if origin.strip()],
    )


settings = get_settings()