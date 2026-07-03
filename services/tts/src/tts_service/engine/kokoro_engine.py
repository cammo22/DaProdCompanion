"""
Wrapper minimale attorno a Kokoro-82M: forza la CPU (budget VRAM riservato a
gemma4), carica la pipeline italiana una sola volta, sintetizza testo in un
array numpy audio mono a 24kHz. Kokoro spezza internamente i testi lunghi in
piu' segmenti: i chunk vengono concatenati in un unico array.
"""

from __future__ import annotations

import os

# Deve avvenire PRIMA di importare kokoro/torch: e' il modo affidabile per
# forzare la CPU indipendentemente da come la libreria seleziona il device.
# __main__.py imposta questa variabile (da Settings.force_cpu_kokoro) prima
# di importare questo modulo.
if os.environ.get("FORCE_CPU_KOKORO", "true").lower() != "false":
    os.environ["CUDA_VISIBLE_DEVICES"] = ""

# eSpeak NG (dipendenza di sistema per il G2P italiano) non e' garantito nel
# PATH subito dopo l'installazione via winget su questa macchina: lo
# aggiungiamo esplicitamente se presente nel percorso standard di Windows.
_ESPEAK_DIR = r"C:\Program Files\eSpeak NG"
if os.path.isdir(_ESPEAK_DIR) and _ESPEAK_DIR not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _ESPEAK_DIR + os.pathsep + os.environ.get("PATH", "")

import numpy as np
from kokoro import KPipeline

SAMPLE_RATE = 24000


class KokoroEngine:
    def __init__(self, lang_code: str = "i") -> None:
        # 'device' esplicito invece di affidarsi solo a CUDA_VISIBLE_DEVICES:
        # quella variabile nasconde la GPU a torch in generale, ma KPipeline
        # supporta un parametro device dedicato ed e' piu' robusto specificarlo
        # qui direttamente (non dipende da un side-effect d'ambiente che in un
        # eseguibile pacchettizzato potrebbe non propagarsi allo stesso modo).
        force_cpu = os.environ.get("FORCE_CPU_KOKORO", "true").lower() != "false"
        self._pipeline = KPipeline(lang_code=lang_code, device="cpu" if force_cpu else None)

    def synthesize(self, text: str, *, voice: str, speed: float = 1.0) -> tuple[np.ndarray, float]:
        """Restituisce (audio_mono_24khz, durata_in_secondi)."""
        chunks = [audio for _, _, audio in self._pipeline(text, voice=voice, speed=speed)]
        if not chunks:
            raise RuntimeError("Kokoro non ha prodotto audio per il testo fornito")
        audio = np.concatenate(chunks)
        duration = len(audio) / SAMPLE_RATE
        return audio, duration

    @property
    def sample_rate(self) -> int:
        return SAMPLE_RATE
