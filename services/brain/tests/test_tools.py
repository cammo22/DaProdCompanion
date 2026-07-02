"""
Test degli strumenti di tool-calling: _recall_graph_entity con un DB SQLite
reale (stesso pattern di test_admin_reset.py/test_graph_writer.py), e
run_chat_with_tools con un OllamaClient finto per verificare il ciclo di
chiamata-esecuzione-richiamata senza toccare la rete.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from companion_shared.db import open_connection

from brain_service.conversation.tools import _recall_graph_entity, run_chat_with_tools
from brain_service.graph.writer import find_or_create_edge, find_or_create_node


@pytest.fixture
def conn(tmp_path: Path):
    connection = open_connection(tmp_path / "test.db")
    yield connection
    connection.close()


def test_recall_graph_entity_not_found(conn):
    assert "Nessuna informazione trovata" in _recall_graph_entity("Marco", conn=conn)


def test_recall_graph_entity_with_no_connections(conn):
    find_or_create_node(conn, node_type="Persona", label="Marco")
    result = _recall_graph_entity("marco", conn=conn)  # case-insensitive
    assert "Marco" in result
    assert "nessuna connessione" in result


def test_recall_graph_entity_with_connections(conn):
    marco = find_or_create_node(conn, node_type="Persona", label="Marco")
    milano = find_or_create_node(conn, node_type="Luogo", label="Milano")
    find_or_create_edge(conn, source_node_id=marco, target_node_id=milano, edge_type="e_avvenuto_in")

    result = _recall_graph_entity("Marco", conn=conn)
    assert "e_avvenuto_in Milano" in result


class FakeOllama:
    def __init__(self, *chat_responses: dict) -> None:
        self._responses = list(chat_responses)
        self.calls: list[list[dict]] = []

    async def chat_raw(self, *, model, messages, num_ctx, tools=None):
        self.calls.append(messages)
        return self._responses.pop(0)

    async def embed(self, *, model, text):
        return [0.1] * 8


def test_run_chat_with_tools_returns_content_directly_when_no_tool_calls():
    ollama = FakeOllama({"role": "assistant", "content": "Ciao!"})
    result = _run(run_chat_with_tools(
        ollama=ollama, model="m", messages=[{"role": "user", "content": "ciao"}], num_ctx=2048,
        conn=None, embedding_model="e",
    ))
    assert result == "Ciao!"
    assert len(ollama.calls) == 1


def test_run_chat_with_tools_executes_recall_graph_entity_and_continues(conn):
    find_or_create_node(conn, node_type="Persona", label="Marco")
    ollama = FakeOllama(
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": "recall_graph_entity", "arguments": {"label": "Marco"}}}],
        },
        {"role": "assistant", "content": "Marco e' un tuo amico."},
    )
    result = _run(run_chat_with_tools(
        ollama=ollama, model="m", messages=[{"role": "user", "content": "chi e' Marco?"}], num_ctx=2048,
        conn=conn, embedding_model="e",
    ))
    assert result == "Marco e' un tuo amico."
    assert len(ollama.calls) == 2
    # Il secondo giro deve contenere il risultato del tool come messaggio 'tool'.
    assert any(m.get("role") == "tool" for m in ollama.calls[1])


def test_run_chat_with_tools_stops_after_max_rounds_and_asks_for_final_answer(conn):
    looping_call = {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"function": {"name": "recall_graph_entity", "arguments": {"label": "Marco"}}}],
    }
    ollama = FakeOllama(looping_call, looping_call, looping_call, {"role": "assistant", "content": "Basta, rispondo."})
    result = _run(run_chat_with_tools(
        ollama=ollama, model="m", messages=[{"role": "user", "content": "..."}], num_ctx=2048,
        conn=conn, embedding_model="e",
    ))
    assert result == "Basta, rispondo."
    assert len(ollama.calls) == 4  # 3 round con tools + 1 richiamata finale senza tools


def _run(coro):
    import asyncio
    return asyncio.run(coro)
