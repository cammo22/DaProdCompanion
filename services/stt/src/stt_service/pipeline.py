"""
Orchestrazione: un segmento audio pronto (da SpeechSegmenter) viene
trascritto. Se la trascrizione contiene il wake-word, o se la finestra di
conversazione e' ancora aperta da uno scambio precedente (vedi
ConversationWindow), viene inoltrata a brain_service come un normale
messaggio di chat. Il resto del parlato (ascoltato sempre, per costruzione)
viene semplicemente scartato qui.
"""

from __future__ import annotations

import logging

import numpy as np

from .brain_client import BrainClient
from .conversation_window import ConversationWindow
from .engine.whisper_engine import WhisperEngine
from .wake_word import contains_wake_word

logger = logging.getLogger("stt")


class VoicePipeline:
    def __init__(
        self,
        *,
        engine: WhisperEngine,
        brain: BrainClient,
        bot_name: str,
        extra_variants: list[str],
        conversation_window: ConversationWindow | None = None,
    ) -> None:
        self._engine = engine
        self._brain = brain
        self._bot_name = bot_name
        self._extra_variants = extra_variants
        self._conversation_window = conversation_window or ConversationWindow()

    async def handle_segment(self, audio: np.ndarray) -> None:
        text = self._engine.transcribe(audio)
        if not text:
            return
        logger.info("Trascritto: %s", text)

        has_wake_word = contains_wake_word(text, self._bot_name, extra_variants=self._extra_variants)
        if not has_wake_word and not self._conversation_window.is_awake():
            return

        if has_wake_word:
            logger.info("Wake-word rilevato, inoltro a brain_service")
        else:
            logger.info("Finestra di conversazione attiva, inoltro senza wake-word")

        # Riazzerato ad ogni inoltro (non solo al primo wake-word): finche' la
        # conversazione resta attiva la finestra si allunga, esattamente come
        # richiesto ("posso rispondere senza dire babbasone" finche' non
        # passano 5 minuti di silenzio).
        self._conversation_window.extend()

        try:
            await self._brain.send_message(text)
        except Exception:
            logger.exception("Invio del messaggio vocale a brain_service fallito")
