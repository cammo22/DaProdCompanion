"""
Orchestrazione: un segmento audio pronto (da SpeechSegmenter) viene
trascritto. Se la trascrizione contiene il wake-word, o se la finestra di
conversazione e' ancora aperta da uno scambio precedente (vedi
ConversationWindow), viene inoltrata a brain_service come un normale
messaggio di chat. Il resto del parlato (ascoltato sempre, per costruzione)
viene semplicemente scartato qui.

Un discorso lungo puo' far scattare il tetto massimo di SpeechSegmenter (non
una pausa reale): in quel caso il segmento arriva con ended_by_silence=False
e va accodato in attesa di un possibile seguito, invece di essere inoltrato
subito come un messaggio a se' stante — altrimenti un unico discorso lungo
verrebbe spezzato in piu' messaggi separati, ognuno con la sua risposta.
Quando invece l'utente si ferma davvero (ended_by_silence=True), si invia
subito: niente attesa aggiuntiva per il caso comune di un enunciato breve.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

import numpy as np

from .audio.segmenter import SpeechSegment
from .brain_client import BrainClient
from .conversation_window import ConversationWindow
from .engine.whisper_engine import WhisperEngine
from .wake_word import contains_wake_word

logger = logging.getLogger("stt")

_MERGE_WINDOW_SECONDS = 3.0


class VoicePipeline:
    def __init__(
        self,
        *,
        engine: WhisperEngine,
        brain: BrainClient,
        bot_name: str,
        extra_variants: list[str],
        conversation_window: ConversationWindow | None = None,
        merge_window_seconds: float = _MERGE_WINDOW_SECONDS,
        on_wake_word: Callable[[], None] = lambda: None,
    ) -> None:
        self._engine = engine
        self._brain = brain
        self._bot_name = bot_name
        self._extra_variants = extra_variants
        self._conversation_window = conversation_window or ConversationWindow()
        self._merge_window_seconds = merge_window_seconds
        self._on_wake_word = on_wake_word
        self._pending_parts: list[str] = []
        self._flush_task: asyncio.Task | None = None

    async def handle_segment(self, segment: SpeechSegment) -> None:
        text = self._engine.transcribe(segment.audio)
        if not text:
            return
        logger.info("Trascritto: %s", text)

        # Se stiamo gia' accumulando il seguito di un discorso troncato dal
        # tetto massimo, questo pezzo va accettato a prescindere: fa gia'
        # parte di un enunciato che ha superato il controllo wake-word/finestra.
        is_continuation = bool(self._pending_parts)
        has_wake_word = contains_wake_word(text, self._bot_name, extra_variants=self._extra_variants)
        if not has_wake_word and not is_continuation and not self._conversation_window.is_awake():
            return

        if has_wake_word:
            logger.info("Wake-word rilevato, inoltro a brain_service")
            self._on_wake_word()
        elif is_continuation:
            logger.info("Discorso ancora in corso (troncato dal tetto massimo), accodo")
        else:
            logger.info("Finestra di conversazione attiva, inoltro senza wake-word")

        # Riazzerato ad ogni inoltro (non solo al primo wake-word): finche' la
        # conversazione resta attiva la finestra si allunga, esattamente come
        # richiesto ("posso rispondere senza dire babbasone" finche' non
        # passano 5 minuti di silenzio).
        self._conversation_window.extend()
        self._pending_parts.append(text)

        if segment.ended_by_silence:
            await self._flush()
        else:
            if self._flush_task is not None:
                self._flush_task.cancel()
            self._flush_task = asyncio.create_task(self._flush_after_pause())

    async def _flush_after_pause(self) -> None:
        try:
            await asyncio.sleep(self._merge_window_seconds)
        except asyncio.CancelledError:
            return  # e' arrivato un altro pezzo dello stesso discorso: si accoda li'
        await self._flush()

    async def _flush(self) -> None:
        if self._flush_task is not None:
            self._flush_task.cancel()
            self._flush_task = None
        if not self._pending_parts:
            return
        text = " ".join(self._pending_parts)
        self._pending_parts = []
        try:
            await self._brain.send_message(text)
        except Exception:
            logger.exception("Invio del messaggio vocale a brain_service fallito")

    async def handle_manual_recording(self, audio: np.ndarray) -> None:
        """Registrazione avviata/fermata a mano dal pulsante 'registra'
        sull'avatar: inoltrata sempre, senza bisogno del wake-word (il click
        stesso e' gia' un'intenzione esplicita dell'utente) e senza passare
        dalla segmentazione automatica (che qui non e' mai stata coinvolta:
        vedi capture.py, il buffer di registrazione la bypassa del tutto)."""
        text = self._engine.transcribe(audio)
        if not text:
            return
        logger.info("Registrazione manuale trascritta: %s", text)
        self._conversation_window.extend()
        try:
            await self._brain.send_message(text)
        except Exception:
            logger.exception("Invio della registrazione manuale a brain_service fallito")

    def start_live_mode(self) -> None:
        """Pulsante 'live': apre subito la finestra di conversazione, come se
        il wake-word fosse appena stato riconosciuto, cosi' l'utente puo'
        iniziare a parlare senza dover dire il nome del bot."""
        self._conversation_window.extend()

    def stop_live_mode(self) -> None:
        """Richiude subito la finestra, senza aspettare i 5 minuti di
        inattivita' (l'utente ha esplicitamente premuto di nuovo 'live')."""
        self._conversation_window.close()
