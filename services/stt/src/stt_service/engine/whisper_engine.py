"""
Wrapper minimale attorno a faster-whisper: modello "small", CPU, int8 (leggero,
nessun impatto sul budget VRAM riservato a gemma4). Trascrive un array audio
mono float32 a 16kHz (frequenza standard per Whisper). Il VAD interno
(vad_filter=True, basato su Silero VAD) scarta i segmenti senza parlato: un
chunk di solo silenzio/rumore produce testo vuoto, non richiede una pipeline
VAD separata per questo primo livello di filtro.

Il VAD da solo non basta: osservato dal vivo che Whisper puo' comunque
"allucinare" del testo su rumore ambiguo che supera la soglia RMS del
segmenter ma non e' parlato reale (es. click di una tastiera meccanica) —
in quel caso produce frasi memorizzate dal training (tipiche: crediti di
sottotitoli) invece di stringa vuota. filter_segments() e' isolata dal resto
apposta per essere testata con dati sintetici, senza dover caricare il
modello vero (stesso approccio di segmenter.py).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000

_NO_SPEECH_PROB_THRESHOLD = 0.6
_AVG_LOGPROB_THRESHOLD = -1.0

# Frasi che Whisper ha visto talmente tante volte in training (crediti di
# sottotitoli di dataset pubblici) che a volte le riproduce con ALTA
# confidenza anche su rumore/silenzio ambiguo: la soglia di confidenza sopra
# non le cattura sempre, serve anche un elenco esplicito dei casi noti.
_KNOWN_HALLUCINATIONS = {
    "sottotitoli a cura di qtss",
    "sottotitoli e revisione a cura di qtss",
    "sottotitoli creati dalla comunita' amara.org",
    "sottotitoli creati dalla comunità amara.org",
}


@dataclass
class SegmentInfo:
    text: str
    no_speech_prob: float
    avg_logprob: float


def _is_low_confidence(segment: SegmentInfo) -> bool:
    """Pattern classico di allucinazione: il modello stesso pensa che
    probabilmente non ci fosse parlato reale (no_speech_prob alto) e non e'
    nemmeno sicuro dei token che ha comunque prodotto (avg_logprob basso).
    Soglie standard raccomandate per Whisper, non inventate — servono
    entrambe insieme perche' no_speech_prob da solo ha falsi positivi su
    parlato reale ma sommesso."""
    return segment.no_speech_prob > _NO_SPEECH_PROB_THRESHOLD and segment.avg_logprob < _AVG_LOGPROB_THRESHOLD


def _is_known_hallucination(text: str) -> bool:
    normalized = text.strip().lower().rstrip(".!? ")
    return normalized in _KNOWN_HALLUCINATIONS


def filter_segments(segments: list[SegmentInfo]) -> str:
    """Applica entrambi i filtri e ricompone il testo tenuto, nello stesso
    ordine dei segmenti in ingresso."""
    kept: list[str] = []
    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        if _is_low_confidence(segment):
            continue
        if _is_known_hallucination(text):
            continue
        kept.append(text)
    return " ".join(kept).strip()


class WhisperEngine:
    def __init__(self, model_size: str = "small") -> None:
        self._model = WhisperModel(model_size, device="cpu", compute_type="int8")

    def transcribe(self, audio: np.ndarray) -> str:
        """'audio' deve essere mono float32 a SAMPLE_RATE Hz. Restituisce il
        testo trascritto, stringa vuota se il VAD non ha rilevato parlato o
        se quel che ha prodotto sembra un'allucinazione (vedi filter_segments)."""
        segments, _ = self._model.transcribe(audio, language="it", vad_filter=True)
        segment_infos = [
            SegmentInfo(text=s.text, no_speech_prob=s.no_speech_prob, avg_logprob=s.avg_logprob)
            for s in segments
        ]
        return filter_segments(segment_infos)
