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
        message = await self.chat_raw(model=model, messages=messages, num_ctx=num_ctx)
        return message["content"]

    async def chat_raw(
        self, *, model: str, messages: list[dict], num_ctx: int, tools: list[dict] | None = None
    ) -> dict:
        """Come chat(), ma restituisce il messaggio completo (non solo il
        testo): serve quando e' presente 'tools', perche' la risposta puo'
        contenere 'tool_calls' invece di (o oltre a) del testo."""
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"num_ctx": num_ctx},
        }
        if tools:
            payload["tools"] = tools
        response = await self._client.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
        return data["message"]

    async def embed(self, *, model: str, text: str) -> list[float]:
        response = await self._client.post("/api/embed", json={"model": model, "input": text})
        response.raise_for_status()
        data = response.json()
        return data["embeddings"][0]

    async def aclose(self) -> None:
        await self._client.aclose()
