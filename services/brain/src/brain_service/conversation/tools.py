"""
Strumenti (tool-calling Ollama) che il companion puo' invocare durante una
normale conversazione, in aggiunta al recupero automatico della memoria
semantica gia' fatto da loop.py prima di ogni risposta. Deliberatamente
molto ristretto: SOLO lettura/scrittura di memoria e grafo, mai esecuzione di
codice, accesso al filesystem oltre quello gia' garantito da FilesystemGuard
altrove, o modifica del codice sorgente dell'app stessa. Ogni nuovo strumento
va aggiunto qui con la stessa cautela.
"""

from __future__ import annotations

import json
import logging
import sqlite3

from .ollama_client import OllamaClient
from ..graph.snapshot import get_graph_snapshot
from ..memory import semantic

logger = logging.getLogger("brain")

_MAX_TOOL_ROUNDS = 3

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": (
                "Salva subito un'informazione importante detta dall'utente in questa "
                "conversazione, senza aspettare il prossimo ciclo di dreaming. Usalo solo "
                "quando l'utente chiede esplicitamente di ricordare qualcosa (es. 'ricorda "
                "che...', 'non dimenticare che...'), non per ogni frase qualunque."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Il fatto da ricordare, in una frase chiara e autosufficiente.",
                    }
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_graph_entity",
            "description": (
                "Cerca cosa sai gia' su una persona, luogo o concetto specifico nel tuo "
                "grafo di conoscenza, tramite il suo nome esatto o quasi esatto. Usalo "
                "quando ti serve un dettaglio strutturato su un'entita' nominata, non per "
                "domande generiche."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "Il nome dell'entita' da cercare (es. 'Marco', 'Napoli')."}
                },
                "required": ["label"],
            },
        },
    },
]


async def _save_memory(text: str, *, conn: sqlite3.Connection, ollama: OllamaClient, embedding_model: str) -> str:
    text = text.strip()
    if not text:
        return "Errore: nessun testo fornito."
    embedding = await ollama.embed(model=embedding_model, text=text)
    semantic.insert_semantic_memory(conn, summary=text, source_event_ids=[], embedding=embedding)
    return f"Memoria salvata: {text}"


def _recall_graph_entity(label: str, *, conn: sqlite3.Connection) -> str:
    label = label.strip()
    if not label:
        return "Errore: nessun nome fornito."

    nodes, edges = get_graph_snapshot(conn)
    node_by_id = {n["id"]: n for n in nodes}
    match = next((n for n in nodes if n["label"].lower() == label.lower()), None)
    if match is None:
        return f"Nessuna informazione trovata su '{label}'."

    connections = []
    for edge in edges:
        if edge["source_node_id"] == match["id"]:
            target = node_by_id.get(edge["target_node_id"])
            if target:
                connections.append(f"{edge['edge_type']} {target['label']}")
        elif edge["target_node_id"] == match["id"]:
            source = node_by_id.get(edge["source_node_id"])
            if source:
                connections.append(f"{source['label']} {edge['edge_type']} {match['label']}")

    if not connections:
        return f"Conosco '{match['label']}' ({match['node_type']}) ma non ho ancora nessuna connessione salvata."
    return f"'{match['label']}' ({match['node_type']}): " + "; ".join(connections)


async def execute_tool_call(
    name: str, arguments: dict, *, conn: sqlite3.Connection, ollama: OllamaClient, embedding_model: str
) -> str:
    """Non lascia mai propagare un'eccezione: un tool che fallisce (es.
    embedding irraggiungibile) degrada a un messaggio di errore restituito al
    modello come risultato del tool, invece di far fallire l'intero turno di
    chat — stessa filosofia di degradazione controllata usata per TTS e
    recupero memoria semantica altrove in loop.py."""
    try:
        if name == "save_memory":
            return await _save_memory(arguments.get("text", ""), conn=conn, ollama=ollama, embedding_model=embedding_model)
        if name == "recall_graph_entity":
            return _recall_graph_entity(arguments.get("label", ""), conn=conn)
        return f"Errore: strumento sconosciuto '{name}'."
    except Exception:
        logger.exception("Esecuzione dello strumento '%s' fallita", name)
        return f"Errore: lo strumento '{name}' non e' riuscito a completare l'operazione."


async def run_chat_with_tools(
    *,
    ollama: OllamaClient,
    model: str,
    messages: list[dict],
    num_ctx: int,
    conn: sqlite3.Connection,
    embedding_model: str,
) -> str:
    """Ciclo tool-calling: chiama il modello, esegue eventuali tool_calls
    restituiti, accoda i risultati come messaggi 'tool' e richiama il modello
    finche' non produce una risposta testuale normale (o si raggiunge il tetto
    massimo di round, per non restare bloccati se il modello continua a
    chiamare strumenti all'infinito)."""
    working_messages = list(messages)

    for _ in range(_MAX_TOOL_ROUNDS):
        message = await ollama.chat_raw(model=model, messages=working_messages, num_ctx=num_ctx, tools=TOOL_DEFINITIONS)
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            return message.get("content", "")

        working_messages.append(message)
        for call in tool_calls:
            function = call.get("function", {})
            tool_name = function.get("name", "")
            raw_arguments = function.get("arguments", {})
            arguments = raw_arguments if isinstance(raw_arguments, dict) else json.loads(raw_arguments or "{}")
            result = await execute_tool_call(tool_name, arguments, conn=conn, ollama=ollama, embedding_model=embedding_model)
            working_messages.append({"role": "tool", "content": result})

    # Tetto massimo raggiunto: chiede una risposta finale senza piu' offrire
    # strumenti, cosi' il modello e' costretto a concludere con del testo.
    final_message = await ollama.chat_raw(model=model, messages=working_messages, num_ctx=num_ctx)
    return final_message.get("content", "")
