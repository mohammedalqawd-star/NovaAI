import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    admin_id: int = int(os.getenv("ADMIN_ID", "8960865438"))
    database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///novabiz.db")
    ai_api_key: str = os.getenv("AI_API_KEY", os.getenv("GROQ_API_KEY", ""))
    ai_base_url: str = os.getenv("AI_BASE_URL", "https://api.groq.com/openai/v1")
    ai_model: str = os.getenv("AI_MODEL", "llama-3.3-70b-versatile")
    free_credits: int = int(os.getenv("FREE_CREDITS", "50"))
    max_message_chars: int = int(os.getenv("MAX_MESSAGE_CHARS", "12000"))
    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "45"))
    search_enabled: bool = os.getenv("SEARCH_ENABLED", "true").lower() == "true"

settings = Settings()

if not settings.bot_token:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
