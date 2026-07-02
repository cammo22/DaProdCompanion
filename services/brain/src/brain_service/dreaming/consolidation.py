"""
Consolidamento della memoria: legge gli episodi non ancora processati, chiede
al modello un riassunto piu' entita'/relazioni in formato JSON strutturato
(vincolato via 'format' sull'API di Ollama, non solo per istruzione nel
prompt), scrive la memoria semantica con il suo embedding e aggiorna il grafo
di conoscenza. Deduplica di nodi/archi delegata a graph.writer.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable
from pathlib import Path

import httpx
from companion_shared.sandbox import FilesystemGuard

from ..graph.writer import find_or_create_edge, find_or_create_node
from ..memory import episodic, semantic
from ..memory.embeddings import generate_embedding
from . import markdown_export

logger = logging.getLogger("brain")

_ENTITY_TYPES = ["Persona", "Evento", "Concetto", "Luogo"]
_EDGE_TYPES = ["conosce", "riguarda", "e_avvenuto_in", "e_collegato_a"]
_MIN_EVENTS_TO_DREAM = 3

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "temp_id": {"type": "string"},
                    "type": {"type": "string", "enum": _ENTITY_TYPES},
                    "label": {"type": "string"},
                },
                "required": ["temp_id", "type", "label"],
            },
        },
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_temp_id": {"type": "string"},
                    "target_temp_id": {"type": "string"},
                    "type": {"type": "string", "enum": _EDGE_TYPES},
                },
                "required": ["source_temp_id", "target_temp_id", "type"],
            },
        },
    },
    "required": ["summary", "entities", "relations"],
}


def _build_transcript(events: list[sqlite3.Row]) -> str:
    lines = []
    for event in events:
        if event["event_type"] == "user_message":
            lines.append(f"Utente: {event['content']}")
        elif event["event_type"] == "bot_reply":
            lines.append(f"Bot: {event['content']}")
        else:
            lines.append(f"[{event['event_type']}] {event['content']}")
    return "\n".join(lines)


def _build_prompt(transcript: str) -> str:
    return (
        "Sei il modulo di consolidamento della memoria di un companion AI. Leggi la "
        "trascrizione qui sotto e produci un JSON con:\n"
        "- 'summary': un riassunto compatto (2-4 frasi) di cosa e' successo o e' stato detto, "
        "utile da ricordare in futuro. Scarta i dettagli poco rilevanti o il rumore. USA SOLO "
        "informazioni presenti nella trascrizione: non inventare mai dettagli, numeri, nomi o "
        "fatti che non ci sono scritti.\n"
        "- 'entities': le entita' nominate nella trascrizione (persone, eventi, concetti, luoghi). "
        "'temp_id' e' SOLO un identificatore interno arbitrario (usa 'e1', 'e2', 'e3', ...): non "
        "deve avere alcun significato, serve solo per collegare le relazioni qui sotto. 'label' e' "
        "invece il nome vero e proprio dell'entita' (es. 'Marco', 'Milano', 'sviluppo software'). Se "
        "l'utente ha detto il proprio nome, usa quel nome come label invece di un termine generico "
        "come 'Utente' o 'utente'.\n"
        "- 'relations': le relazioni tra le entita' sopra, riferendole tramite i loro temp_id.\n\n"
        "Se non ci sono entita' o relazioni rilevanti, lascia le liste vuote piuttosto che inventarle.\n\n"
        f"Trascrizione:\n{transcript}"
    )


async def run_dreaming_cycle(
    *,
    conn: sqlite3.Connection,
    ollama_host: str,
    brain_model_tag: str,
    embedding_model_tag: str,
    num_ctx: int,
    guard: FilesystemGuard,
    sandbox_root: Path,
    on_event: Callable[[str, dict], None] | None = None,
) -> int:
    """Esegue un ciclo di consolidamento. Restituisce il numero di episodi
    consolidati (0 se non c'era nulla da fare o qualcosa e' andato storto).
    'on_event' (opzionale) viene chiamato con 'dreaming-started' solo se c'e'
    davvero lavoro da fare, e con 'dreaming-finished' alla fine in ogni caso
    (anche in caso di errore, tramite finally) — e' cosi' che Electron sa
    quando mostrare/nascondere la bubble "sognando..." sull'avatar."""
    events = episodic.get_unconsolidated_events(conn)
    if len(events) < _MIN_EVENTS_TO_DREAM:
        logger.info("Dreaming: solo %d episodi non consolidati, salto questo giro", len(events))
        return 0

    if on_event:
        on_event("dreaming-started", {})

    consolidated_count = 0
    try:
        transcript = _build_transcript(events)
        prompt = _build_prompt(transcript)

        async with httpx.AsyncClient(base_url=ollama_host, timeout=180.0) as client:
            response = await client.post(
                "/api/chat",
                json={
                    "model": brain_model_tag,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "format": _RESPONSE_SCHEMA,
                    # num_predict esplicito: senza, il default di Ollama puo' troncare
                    # a meta' un riassunto+entita'+relazioni su transcript lunghi (osservato
                    # con 56 episodi: il riassunto si interrompeva a meta' frase). La
                    # generazione vincolata dallo schema produce comunque JSON
                    # sintatticamente valido anche se troncata, quindi il taglio non fa
                    # fallire il parsing ma restituisce contenuto incompleto.
                    "options": {"num_ctx": num_ctx, "num_predict": 2048},
                },
            )
            response.raise_for_status()
            content = response.json()["message"]["content"]

            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                logger.error("Dreaming: risposta del modello non era JSON valido, salto questo giro")
                return 0

            summary = parsed.get("summary", "").strip()
            if not summary:
                logger.info("Dreaming: nessun riassunto prodotto, salto questo giro")
                return 0

            embedding = await generate_embedding(client, model=embedding_model_tag, text=summary)

        event_ids = [event["id"] for event in events]
        semantic.insert_semantic_memory(conn, summary=summary, source_event_ids=event_ids, embedding=embedding)

        temp_id_to_node_id: dict[str, int] = {}
        for entity in parsed.get("entities", []):
            node_id = find_or_create_node(conn, node_type=entity["type"], label=entity["label"])
            temp_id_to_node_id[entity["temp_id"]] = node_id

        graph_changed = bool(parsed.get("entities"))
        for relation in parsed.get("relations", []):
            source_id = temp_id_to_node_id.get(relation["source_temp_id"])
            target_id = temp_id_to_node_id.get(relation["target_temp_id"])
            if source_id is None or target_id is None:
                continue  # temp_id sconosciuto: il modello ha citato un'entita' non elencata sopra
            find_or_create_edge(
                conn, source_node_id=source_id, target_node_id=target_id, edge_type=relation["type"]
            )

        episodic.mark_consolidated(conn, event_ids)

        # Export in markdown in aggiunta a SQLite (non al posto): non deve
        # far fallire il ciclo se scrivere su disco va storto, il
        # consolidamento vero e proprio e' gia' andato a buon fine sopra.
        try:
            markdown_export.write_dream_summary(summary, guard=guard, sandbox_root=sandbox_root)
            if graph_changed:
                markdown_export.write_entity_files(conn, guard=guard, sandbox_root=sandbox_root)
        except Exception:
            logger.exception("Dreaming: export in markdown fallito, il consolidamento resta comunque valido")

        if graph_changed and on_event:
            on_event("graph-updated", {})

        consolidated_count = len(event_ids)
        logger.info(
            "Dreaming: consolidati %d episodi in 1 memoria semantica, %d entita', %d relazioni",
            consolidated_count,
            len(parsed.get("entities", [])),
            len(parsed.get("relations", [])),
        )
        return consolidated_count
    finally:
        if on_event:
            on_event("dreaming-finished", {"consolidated_events": consolidated_count})
