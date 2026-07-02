"""Client minimale verso l'API locale di tts_service."""

from __future__ import annotations

import httpx


class TtsClient:
    def __init__(self, host: str, *, timeout: float = 60.0) -> None:
        self._client = httpx.AsyncClient(base_url=host.rstrip("/"), timeout=timeout)

    async def speak(self, text: str) -> tuple[str, float]:
        """Restituisce (audio_path, duration_seconds)."""
        response = await self._client.post("/speak", json={"text": text})
        response.raise_for_status()
        data = response.json()
        return data["audio_path"], data["duration_seconds"]

    async def aclose(self) -> None:
        await self._client.aclose()
