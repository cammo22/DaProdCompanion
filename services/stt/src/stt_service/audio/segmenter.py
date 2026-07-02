"""
Segmentazione del parlato basata sull'energia (RMS) del segnale: non serve un
modello VAD dedicato per questo primo livello, solo una soglia di volume.
Isolata dal loop di cattura vero e proprio (vedi capture.py) apposta per
poter essere testata con array audio sintetici, senza un microfono reale.
faster-whisper applica comunque il proprio VAD (Silero) come secondo filtro
piu' preciso al momento della trascrizione.
"""

from __future__ import annotations

import numpy as np

_SILENCE_RMS_THRESHOLD = 0.01
_SILENCE_BLOCKS_TO_END_SEGMENT = 3  # con blocchi da 0.5s, ~1.5s di silenzio chiude l'enunciato
_MAX_SEGMENT_BLOCKS = 30  # ~15s: chiude comunque, non cresce all'infinito
_MIN_SPEECH_BLOCKS = 2  # scarta blip troppo brevi (< ~1s)


class SpeechSegmenter:
    def __init__(self) -> None:
        self._buffer: list[np.ndarray] = []
        self._loud_block_count = 0
        self._silence_run = 0
        self._speaking = False

    @property
    def is_speaking(self) -> bool:
        """Esposto per capture.py: rileva li' le transizioni (silenzio->parlato
        e viceversa) confrontando questo valore prima/dopo push_block, per
        pilotare lo stato "in ascolto" dell'avatar senza toccare la logica di
        segmentazione qui sopra (gia' testata con audio sintetico)."""
        return self._speaking

    def push_block(self, block: np.ndarray) -> np.ndarray | None:
        """Restituisce l'audio completo quando un enunciato si conclude,
        altrimenti None (segmento ancora in corso o silenzio prolungato)."""
        rms = float(np.sqrt(np.mean(np.square(block))))
        is_loud = rms >= _SILENCE_RMS_THRESHOLD

        if is_loud:
            self._buffer.append(block)
            self._loud_block_count += 1
            self._speaking = True
            self._silence_run = 0
        elif self._speaking:
            self._buffer.append(block)  # include un po' di coda silenziosa
            self._silence_run += 1

        if self._speaking and self._silence_run >= _SILENCE_BLOCKS_TO_END_SEGMENT:
            return self._finalize()
        if self._speaking and len(self._buffer) >= _MAX_SEGMENT_BLOCKS:
            return self._finalize()
        return None

    def _finalize(self) -> np.ndarray | None:
        segment_blocks = self._buffer
        loud_block_count = self._loud_block_count
        self._buffer = []
        self._loud_block_count = 0
        self._speaking = False
        self._silence_run = 0
        # Il conteggio minimo guarda solo ai blocchi rumorosi, non al totale:
        # la coda di silenzio inclusa per rilevare la fine dell'enunciato non
        # deve far passare un singolo blip come se fosse parlato vero.
        if loud_block_count < _MIN_SPEECH_BLOCKS:
            return None
        return np.concatenate(segment_blocks)
