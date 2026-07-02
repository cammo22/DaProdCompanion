"""
Confronto testuale approssimato condiviso tra servizi: sia brain (corregge le
storpiature del proprio nome nelle risposte del modello) sia stt (riconosce il
proprio nome nelle trascrizioni vocali, che Whisper puo' rendere in modo
leggermente impreciso) hanno bisogno dello stesso confronto "e' un refuso di
una lettera o due di questa parola target?".
"""

from __future__ import annotations


def is_close_variant(word: str, target: str) -> bool:
    """True se 'word' sembra un tentativo, leggermente storpiato, di scrivere
    'target': stessa lunghezza (+/-1) e la maggior parte dei caratteri
    coincide nella stessa posizione (es. 'Babbaxone' rispetto a 'Babbasone')."""
    w, t = word.lower(), target.lower()
    if w == t or len(t) < 4:
        return False
    if abs(len(w) - len(t)) > 1:
        return False
    common = sum(1 for a, b in zip(w, t) if a == b)
    return common >= len(t) - 2
