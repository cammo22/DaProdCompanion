"""
Bus di eventi interni: i moduli che generano eventi (dreaming, loop di
conversazione) pubblicano qui; l'endpoint WebSocket si iscrive e li inoltra a
Electron. Disaccoppia chi genera un evento da chi lo consuma (oggi solo
Electron via /ws, ma nulla lo impone in futuro).
"""

from __future__ import annotations

import asyncio
import json


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def publish(self, event_type: str, payload: dict | None = None) -> None:
        message = json.dumps({"type": event_type, **(payload or {})}, ensure_ascii=False)
        for queue in self._subscribers:
            queue.put_nowait(message)
