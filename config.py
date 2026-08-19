import os
from dataclasses import dataclass


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    admin_id: int = _int_env("ADMIN_ID", 8960865438)
    database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///novabiz.db")
    ai_api_key: str = os.getenv("AI_API_KEY", os.getenv("GROQ_API_KEY", ""))
    ai_base_url: str = os.getenv("AI_BASE_URL", "https://api.groq.com/openai/v1")
    ai_model: str = os.getenv("AI_MODEL", "llama-3.3-70b-versatile")
    fallback_api_key: str = os.getenv("FALLBACK_AI_API_KEY", "")
    fallback_base_url: str = os.getenv("FALLBACK_AI_BASE_URL", "https://api.openai.com/v1")
    fallback_model: str = os.getenv("FALLBACK_AI_MODEL", "gpt-4o-mini")
    vision_model: str = os.getenv("VISION_MODEL", "")
    speech_model: str = os.getenv("SPEECH_MODEL", "whisper-1")
    free_credits: int = _int_env("FREE_CREDITS", 50)
    max_message_chars: int = _int_env("MAX_MESSAGE_CHARS", 12000)
    request_timeout: int = _int_env("REQUEST_TIMEOUT", 45)
    rate_limit_per_minute: int = _int_env("RATE_LIMIT_PER_MINUTE", 20)
    search_enabled: bool = os.getenv("SEARCH_ENABLED", "true").lower() == "true"


settings = Settings()


def validate_runtime_config() -> None:
    if not settings.bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
