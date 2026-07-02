"""
Cattura microfono continua: usa sounddevice per leggere blocchi audio e li
passa a SpeechSegmenter per la segmentazione. Non testabile in isolamento
senza un microfono reale (a differenza di SpeechSegmenter, che e' testato
con array sintetici in test_segmenter.py) — verificato dal vivo dall'utente.
"""

from __future__ import annotations

import logging
import queue
from collections.abc import Callable

import numpy as np
import sounddevice as sd

from ..engine.whisper_engine import SAMPLE_RATE
from .segmenter import SpeechSegment, SpeechSegmenter

logger = logging.getLogger("stt")

_BLOCK_DURATION_S = 0.5
_BLOCK_SIZE = int(SAMPLE_RATE * _BLOCK_DURATION_S)


def listen_loop(
    on_segment: Callable[[SpeechSegment], None],
    *,
    device_index: int | None = None,
    stop_flag: Callable[[], bool] = lambda: False,
    on_listening_start: Callable[[], None] = lambda: None,
    on_listening_end: Callable[[], None] = lambda: None,
    is_muted: Callable[[], bool] = lambda: False,
    is_recording: Callable[[], bool] = lambda: False,
    on_recording_complete: Callable[[np.ndarray], None] = lambda audio: None,
) -> None:
    """Blocca il thread corrente ascoltando dal microfono, chiamando
    on_segment() ogni volta che SpeechSegmenter conclude un enunciato. Va
    eseguito in un thread dedicato (e' bloccante), mai nell'event loop
    asyncio principale. 'stop_flag' permette uno spegnimento pulito.

    on_listening_start/end segnalano le transizioni silenzio<->parlato (per
    lo stato "in ascolto" dell'avatar): confrontano SpeechSegmenter.is_speaking
    prima e dopo ogni blocco invece di modificare la logica di segmentazione,
    che resta testata in isolamento con audio sintetico. Quando is_muted()
    e' vero i segmenti vengono comunque scartati qui (non solo a valle in
    pipeline.py) cosi' l'avatar non mostra "in ascolto" a microfono muto.

    Mentre is_recording() e' vero (pulsante "registra" premuto sull'avatar) i
    blocchi finiscono in un buffer dedicato, bypassando del tutto
    SpeechSegmenter: l'utente ha gia' dato un'intenzione esplicita col click,
    non serve ne' la soglia di silenzio ne' il wake-word. Al rilascio del
    pulsante, tutto il buffer accumulato viene consegnato in un colpo solo a
    on_recording_complete()."""
    segmenter = SpeechSegmenter()
    block_queue: queue.Queue[np.ndarray] = queue.Queue()

    def _callback(indata: np.ndarray, frames: int, time_info: object, status: sd.CallbackFlags) -> None:
        if status:
            logger.warning("Stato non ok dallo stream audio: %s", status)
        block_queue.put(indata[:, 0].copy())

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=_BLOCK_SIZE,
        device=device_index,
        callback=_callback,
    ):
        logger.info("In ascolto dal microfono (device=%s)...", device_index if device_index is not None else "default")
        was_speaking = False
        # Tiene traccia se l'avatar e' stato davvero avvisato dell'inizio
        # ascolto, indipendentemente dal mute corrente: se il microfono viene
        # mutato a meta' enunciato, il mute al momento della finalizzazione
        # sarebbe vero e negherebbe l'evento di fine, lasciando l'avatar
        # bloccato su "in ascolto" per sempre. Confrontando invece con questo
        # flag, ogni on_listening_start ha sempre il suo on_listening_end.
        listening_signaled = False
        recording_buffer: list[np.ndarray] = []
        was_recording = False
        while not stop_flag():
            try:
                block = block_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            recording_now = is_recording()
            if recording_now:
                recording_buffer.append(block)
                was_recording = True
                continue
            if was_recording:
                was_recording = False
                if recording_buffer:
                    on_recording_complete(np.concatenate(recording_buffer))
                    recording_buffer = []
                # niente 'continue': questo blocco (gia' non piu' in
                # registrazione) prosegue nella gestione normale sotto.

            muted = is_muted()
            segment = segmenter.push_block(block)

            is_speaking_now = segmenter.is_speaking
            if is_speaking_now and not was_speaking and not muted:
                on_listening_start()
                listening_signaled = True
            elif was_speaking and not is_speaking_now and listening_signaled:
                on_listening_end()
                listening_signaled = False
            was_speaking = is_speaking_now

            if segment is not None and not muted:
                on_segment(segment)
