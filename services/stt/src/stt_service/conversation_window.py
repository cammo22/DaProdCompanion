"""
Finestra di conversazione senza wake-word: una volta riconosciuto il nome del
bot, resta "sveglia" per _AWAKE_SECONDS. Durante quella finestra ogni
enunciato successivo viene inoltrato a brain_service anche senza ripetere il
nome, e ogni inoltro riazzera il timer. Scaduta la finestra, serve di nuovo
il wake-word. Isolata dal resto della pipeline (che dipende da microfono e
tempo reale) apposta per essere testata con un orologio finto, senza dover
aspettare 5 minuti veri — stesso approccio di segmenter.py.
"""

from __future__ import annotations

import time
from collections.abc import Callable

_AWAKE_SECONDS = 300.0  # 5 minuti


class ConversationWindow:
    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._awake_until: float | None = None

    def is_awake(self) -> bool:
        return self._awake_until is not None and self._clock() < self._awake_until

    def extend(self) -> None:
        self._awake_until = self._clock() + _AWAKE_SECONDS
