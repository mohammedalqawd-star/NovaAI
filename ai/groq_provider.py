import asyncio
from typing import Any

import aiohttp

from config import settings


class AIEngine:
    """Async OpenAI-compatible client configured for Groq."""

    def __init__(self) -> None:
        self.api_key = settings.ai_api_key
        self.base_url = settings.ai_base_url.rstrip("/")
        self.model = settings.ai_model
        self.fallback_key = settings.fallback_api_key
        self.fallback_url = settings.fallback_base_url.rstrip("/")
        self.fallback_model = settings.fallback_model

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    @property
    def fallback(self) -> bool:
        return bool(self.fallback_key)

    async def _chat(self, api_key: str, base_url: str, model: str, messages: list[dict[str, Any]]) -> str:
        if not api_key:
            raise RuntimeError("AI provider key is not configured")
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
        }
        timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(f"{base_url}/chat/completions", json=payload, headers=headers) as response:
                body = await response.text()
                if response.status >= 400:
                    raise RuntimeError(f"AI provider HTTP {response.status}: {body[:500]}")
                data = await response.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Invalid AI provider response") from exc

    async def answer(self, messages: list[dict[str, Any]]) -> str:
        """Use Groq first, then an optional OpenAI-compatible fallback."""
        try:
            return await self._chat(self.api_key, self.base_url, self.model, messages)
        except Exception as primary_error:
            if not self.fallback_key:
                raise primary_error
            return await self._chat(self.fallback_key, self.fallback_url, self.fallback_model, messages)

    async def transcribe(self, audio: bytes) -> str:
        if not self.api_key:
            raise RuntimeError("AI provider key is not configured")
        timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
        data = aiohttp.FormData()
        data.add_field("file", audio, filename="voice.ogg", content_type="audio/ogg")
        data.add_field("model", settings.speech_model)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(f"{self.base_url}/audio/transcriptions", data=data, headers=headers) as response:
                body = await response.text()
                if response.status >= 400:
                    raise RuntimeError(f"Groq transcription HTTP {response.status}: {body[:500]}")
                result = await response.json()
        return str(result.get("text", "")).strip()

    async def close(self) -> None:
        await asyncio.sleep(0)
