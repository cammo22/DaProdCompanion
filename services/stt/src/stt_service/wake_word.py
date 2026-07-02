"""
Rilevamento del wake-word: il companion ascolta sempre, ma genera una
risposta solo se sente il proprio nome nella trascrizione (gating economico
prima di coinvolgere brain/Ollama). Riusa lo stesso confronto "variante
vicina" di brain_service (companion_shared.text_matching), perche' Whisper
puo' trascrivere il nome in modo leggermente impreciso, come fa il LLM nello
scriverlo. 'extra_variants' accoglie le trascrizioni osservate durante la
calibrazione (vedi settings) per la voce/microfono specifici dell'utente.
"""

from __future__ import annotations

import re

from companion_shared.text_matching import is_close_variant


def contains_wake_word(text: str, bot_name: str, *, extra_variants: list[str] | None = None) -> bool:
    normalized_text = text.lower()

    # Le varianti note (il nome esatto o quelle raccolte in calibrazione)
    # possono essere frasi di piu' parole: Whisper a volte spezza un nome
    # insolito in piu' token separati (es. "bab a sone"). Si cercano come
    # sottostringa dell'intera trascrizione, non parola per parola.
    known_variants = {bot_name.lower(), *(v.lower() for v in (extra_variants or []))}
    if any(variant in normalized_text for variant in known_variants):
        return True

    # Fallback: fuzzy match parola per parola per refusi di una singola
    # parola non ancora raccolti dalla calibrazione.
    words = re.findall(r"\b\w+\b", text, flags=re.UNICODE)
    return any(is_close_variant(word, bot_name) for word in words)
