"""Client minimale verso l'API locale di stt_service (stesso pattern di
tts_client.py). Usato solo dalla modalita' Quantum per zittire l'ascolto
mentre e' attiva: se stt_service non e' raggiungibile la chiamata fallisce in
modo silenzioso lato chiamante (vedi quantum/mode.py), non deve mai bloccare
l'attivazione/disattivazione della modalita'."""

from __future__ import annotations

import httpx


class SttClient:
    def __init__(self, host: str, *, timeout: float = 10.0) -> None:
        self._client = httpx.AsyncClient(base_url=host.rstrip("/"), timeout=timeout)

    async def set_quantum_mute(self, muted: bool) -> None:
        response = await self._client.post("/mic/quantum-mute", json={"muted": muted})
        response.raise_for_status()

    async def aclose(self) -> None:
        await self._client.aclose()
