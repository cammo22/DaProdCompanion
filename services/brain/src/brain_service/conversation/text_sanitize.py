"""
Post-processing sul testo generato dal modello: correzione delle occasionali
storpiature del nome del companion, e ripulitura del testo prima di passarlo
alla sintesi vocale (emoji e asterischi di enfasi markdown: nel testo mostrato
in chat restano entrambi, l'utente li vuole visibili, solo non li vuole
letti/pronunciati da Kokoro).
"""

from __future__ import annotations

import re

from companion_shared.text_matching import is_close_variant

_EMOJI_PATTERN = re.compile(
    "["
    "\U0001f300-\U0001f5ff"
    "\U0001f600-\U0001f64f"
    "\U0001f680-\U0001f6ff"
    "\U0001f700-\U0001f7ff"
    "\U0001f800-\U0001f8ff"
    "\U0001f900-\U0001f9ff"
    "\U0001fa00-\U0001faff"
    "\U00002600-\U000026ff"
    "\U00002700-\U000027bf"
    "\U0001f1e6-\U0001f1ff"
    "\U00002300-\U000023ff"
    "\U0000fe0f"
    "\U0000200d"
    "]+",
    flags=re.UNICODE,
)


_THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>", flags=re.DOTALL | re.IGNORECASE)


def strip_reasoning(text: str) -> str:
    """Rimuove eventuali blocchi <think>...</think> dal testo generato: con
    'think': False (vedi ollama_client) i modelli pensanti non dovrebbero
    emetterli, ma alcuni li includono comunque nel contenuto a seconda della
    versione — questa e' la rete di sicurezza perche' il ragionamento interno
    non finisca MAI nel messaggio mostrato/letto all'utente. Applicata al
    testo della risposta prima di tutto il resto (a differenza di strip_emoji/
    strip_markdown_emphasis, che valgono solo per l'input vocale)."""
    return _THINK_BLOCK_PATTERN.sub("", text).strip()


def strip_emoji(text: str) -> str:
    """Rimuove le emoji dal testo da inviare alla sintesi vocale."""
    without_emoji = _EMOJI_PATTERN.sub("", text)
    return re.sub(r" {2,}", " ", without_emoji).strip()


def strip_markdown_emphasis(text: str) -> str:
    """Toglie gli asterischi di enfasi markdown (**grassetto**, *corsivo*) dal
    testo da inviare alla sintesi vocale: il carattere resta nel testo
    mostrato in chat, ma Kokoro non deve leggerlo."""
    return text.replace("*", "")


def prepare_for_speech(text: str) -> str:
    """Applica tutte le ripuliture pensate solo per l'input della sintesi
    vocale (mai per il testo mostrato in chat, che resta invariato)."""
    return strip_emoji(strip_markdown_emphasis(text))


def correct_bot_name(text: str, bot_name: str) -> str:
    """Corregge le occasionali storpiature del nome del companion da parte del
    modello, sostituendole con la grafia esatta scelta dall'utente. Rete di
    sicurezza oltre al rinforzo gia' presente nel system prompt: i modelli
    piccoli a volte 're-inventano' un nome insolito invece di ripeterlo alla
    lettera."""

    def _replace(match: re.Match[str]) -> str:
        word = match.group(0)
        return bot_name if is_close_variant(word, bot_name) else word

    return re.sub(r"\b\w+\b", _replace, text, flags=re.UNICODE)
