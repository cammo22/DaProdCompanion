"""
Orchestrazione: un segmento audio pronto (da SpeechSegmenter) viene
trascritto, e se la trascrizione contiene il wake-word viene inoltrata a
brain_service come un normale messaggio di chat. Il resto del parlato
(ascoltato sempre, per costruzione) viene semplicemente scartato qui.
"""

from __future__ import annotations

import logging

import numpy as np

from .brain_client import BrainClient
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
    ) -> None:
        self._engine = engine
        self._brain = brain
        self._bot_name = bot_name
        self._extra_variants = extra_variants

    async def handle_segment(self, audio: np.ndarray) -> None:
        text = self._engine.transcribe(audio)
        if not text:
            return
        logger.info("Trascritto: %s", text)

        if not contains_wake_word(text, self._bot_name, extra_variants=self._extra_variants):
            return

        logger.info("Wake-word rilevato, inoltro a brain_service")
        try:
            await self._brain.send_message(text)
        except Exception:
            logger.exception("Invio del messaggio vocale a brain_service fallito")
