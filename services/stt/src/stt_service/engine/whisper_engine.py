"""
Wrapper minimale attorno a faster-whisper: modello "small", CPU, int8 (leggero,
nessun impatto sul budget VRAM riservato a gemma4). Trascrive un array audio
mono float32 a 16kHz (frequenza standard per Whisper). Il VAD interno
(vad_filter=True, basato su Silero VAD) scarta i segmenti senza parlato: un
chunk di solo silenzio/rumore produce testo vuoto, non richiede una pipeline
VAD separata per questo primo livello di filtro.
"""

from __future__ import annotations

import numpy as np
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000


class WhisperEngine:
    def __init__(self, model_size: str = "small") -> None:
        self._model = WhisperModel(model_size, device="cpu", compute_type="int8")

    def transcribe(self, audio: np.ndarray) -> str:
        """'audio' deve essere mono float32 a SAMPLE_RATE Hz. Restituisce il
        testo trascritto, stringa vuota se il VAD non ha rilevato parlato."""
        segments, _ = self._model.transcribe(audio, language="it", vad_filter=True)
        return " ".join(segment.text.strip() for segment in segments).strip()
