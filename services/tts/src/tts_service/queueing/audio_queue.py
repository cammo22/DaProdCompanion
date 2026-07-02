"""
Serializza le richieste di sintesi verso Kokoro: una alla volta, eseguite in
un thread separato per non bloccare l'event loop (cosi' /health resta
reattivo anche mentre una sintesi e' in corso). Le richieste in eccesso
attendono semplicemente il rilascio del lock, che e' la coda richiesta dalla
specifica ("niente sovrapposizioni audio").
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class AudioQueue:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    async def synthesize(self, fn: Callable[[], T]) -> T:
        async with self._lock:
            return await asyncio.to_thread(fn)
