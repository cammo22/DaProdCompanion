"""
Client minimale verso l'API locale di Ollama. Usa /api/chat (non /api/generate)
perche' gestisce nativamente la cronologia a turni, il caso d'uso del loop di
conversazione.
"""

from __future__ import annotations

import httpx


class OllamaClient:
    def __init__(self, host: str, *, timeout: float = 120.0) -> None:
        self._client = httpx.AsyncClient(base_url=host.rstrip("/"), timeout=timeout)

    async def chat(self, *, model: str, messages: list[dict[str, str]], num_ctx: int) -> str:
        response = await self._client.post(
            "/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"num_ctx": num_ctx},
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]

    async def embed(self, *, model: str, text: str) -> list[float]:
        response = await self._client.post("/api/embed", json={"model": model, "input": text})
        response.raise_for_status()
        data = response.json()
        return data["embeddings"][0]

    async def aclose(self) -> None:
        await self._client.aclose()
