"""
Ciclo di conversazione: recupera i ricordi semantici rilevanti (se ce ne sono
gia' di consolidati dal dreaming) piu' la coda recente della memoria episodica
grezza, chiama Ollama, salva sia il messaggio dell'utente sia la risposta come
nuovi eventi episodici, poi chiede la sintesi vocale a tts.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass

from companion_shared.config import Settings

from ..memory import episodic, semantic
from .ollama_client import OllamaClient
from .prompt_templates import build_system_prompt
from .text_sanitize import correct_bot_name, prepare_for_speech, strip_reasoning
from .tools import run_chat_with_tools
from .tts_client import TtsClient

logger = logging.getLogger("brain")


@dataclass
class ChatResult:
    reply: str
    audio_path: str | None
    duration_seconds: float | None
    used_memory: bool


async def _retrieve_relevant_memories(
    *, conn: sqlite3.Connection, ollama: OllamaClient, embedding_model: str, query_text: str
) -> list[str]:
    """Recupero best-effort: se la memoria semantica e' vuota o l'embedding
    fallisce per qualsiasi motivo, la conversazione prosegue comunque solo con
    la cronologia recente (degrado controllato, come per il tts)."""
    try:
        query_embedding = await ollama.embed(model=embedding_model, text=query_text)
        return semantic.search_relevant_memories(conn, query_embedding=query_embedding, limit=5)
    except Exception as exc:
        logger.warning("Recupero memoria semantica fallito, proseguo solo con la cronologia: %s", exc)
        return []


async def handle_user_message(
    *,
    user_message: str,
    settings: Settings,
    conn: sqlite3.Connection,
    ollama: OllamaClient,
    tts: TtsClient | None = None,
    history_limit: int = 20,
) -> ChatResult:
    """L'audio e' opzionale: se la sintesi fallisce, la risposta testuale resta
    comunque valida (degrado controllato, non si blocca la chat per un
    problema di tts_service). 'used_memory' indica se il recupero semantico ha
    trovato ricordi rilevanti usati per rispondere (Electron lo mostra come
    piccolo indicatore grafico)."""
    system_prompt = build_system_prompt(settings.bot_name)

    relevant_memories = await _retrieve_relevant_memories(
        conn=conn,
        ollama=ollama,
        embedding_model=settings.embedding_model_tag,
        query_text=user_message,
    )
    if relevant_memories:
        memory_bullets = "\n".join(f"- {m}" for m in relevant_memories)
        system_prompt += (
            "\n\nRicordi rilevanti da conversazioni passate (usali solo se pertinenti al "
            f"messaggio attuale, non citarli meccanicamente):\n{memory_bullets}"
        )

    recent = episodic.get_recent_events(conn, limit=history_limit)

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for event in reversed(recent):
        if event["event_type"] == "user_message":
            messages.append({"role": "user", "content": event["content"]})
        elif event["event_type"] == "bot_reply":
            messages.append({"role": "assistant", "content": event["content"]})
    messages.append({"role": "user", "content": user_message})

    episodic.log_event(conn, event_type="user_message", content=user_message, source="brain")

    reply = await run_chat_with_tools(
        ollama=ollama,
        model=settings.brain_model_tag,
        messages=messages,
        num_ctx=settings.brain_model_num_ctx,
        conn=conn,
        embedding_model=settings.embedding_model_tag,
    )
    # strip_reasoning PRIMA di correct_bot_name: cosi' un eventuale blocco
    # <think> non finisce ne' nel testo mostrato, ne' salvato in episodic, ne'
    # letto dal TTS.
    reply = correct_bot_name(strip_reasoning(reply), settings.bot_name)

    episodic.log_event(conn, event_type="bot_reply", content=reply, source="brain")

    audio_path: str | None = None
    duration_seconds: float | None = None
    if tts is not None:
        try:
            # Emoji e asterischi di enfasi restano nel testo mostrato in chat
            # (reply), ma non vengono letti da Kokoro: a tts si passa solo la
            # versione ripulita.
            audio_path, duration_seconds = await tts.speak(prepare_for_speech(reply))
        except Exception as exc:
            logger.warning("Sintesi vocale non riuscita, proseguo solo con il testo: %s", exc)

    return ChatResult(
        reply=reply,
        audio_path=audio_path,
        duration_seconds=duration_seconds,
        used_memory=bool(relevant_memories),
    )
