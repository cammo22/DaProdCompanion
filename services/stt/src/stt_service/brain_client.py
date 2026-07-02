"""
Client minimale verso l'API locale di brain_service: stt si limita a
inoltrare il testo riconosciuto, esattamente come farebbe la chat testuale di
Electron (stesso endpoint POST /chat, brain non sa/non deve sapere se il
messaggio arriva da tastiera o voce).
"""

from __future__ import annotations

import httpx


class BrainClient:
    def __init__(self, host: str, *, timeout: float = 60.0) -> None:
        self._client = httpx.AsyncClient(base_url=host.rstrip("/"), timeout=timeout)

    async def send_message(self, text: str) -> None:
        # source="voice" fa si' che brain pubblichi la risposta (testo + audio)
        # sul bus eventi invece di lasciarla solo nel corpo di questa risposta
        # HTTP, che qui non viene letto: stt e' fire-and-forget verso brain,
        # e' Electron ad ascoltare l'evento per far parlare/mostrare l'avatar.
        response = await self._client.post("/chat", json={"message": text, "source": "voice"})
        response.raise_for_status()

    async def notify_event(self, event_type: str) -> None:
        """Inoltra un evento di stato del microfono (in ascolto/fine ascolto)
        a brain, che lo ripubblica sul suo canale WS verso Electron: solo
        brain parla con Electron in push, per design (vedi architettura.md)."""
        response = await self._client.post("/events/voice", json={"type": event_type})
        response.raise_for_status()

    async def notify_partial_transcript(self, text: str) -> None:
        """Anteprima di quello che l'utente sta dicendo (vedi
        VoicePipeline.on_partial_transcript), inoltrata a brain con lo stesso
        criterio di notify_event: solo brain parla con Electron in push."""
        response = await self._client.post("/events/partial-transcript", json={"text": text})
        response.raise_for_status()

    async def aclose(self) -> None:
        await self._client.aclose()
