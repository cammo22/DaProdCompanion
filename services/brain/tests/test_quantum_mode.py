"""
Test della parte pura/filesystem di Quantum mode (niente chiamate di rete
reali a Ollama, coerente con la filosofia di test del progetto: il ciclo
vero e proprio, che dipende da httpx/Ollama, si verifica dal vivo come il
resto del loop di conversazione)."""

from __future__ import annotations

from pathlib import Path

import pytest
from companion_shared.sandbox import FilesystemGuard

from companion_shared.db import open_connection

from brain_service.graph.snapshot import get_graph_snapshot
from brain_service.quantum.mode import (
    QuantumMode,
    _build_iteration_prompt,
    _read_handoff_note,
    _write_handoff_note,
)


@pytest.fixture
def sandbox_root(tmp_path):
    return tmp_path / "sandbox"


@pytest.fixture
def guard(sandbox_root):
    return FilesystemGuard(sandbox_root, service="test")


@pytest.fixture
def conn(tmp_path):
    connection = open_connection(tmp_path / "test.db")
    yield connection
    connection.close()


def _make_quantum(conn, sandbox_root, on_event=None) -> QuantumMode:
    # Solo _apply_iteration e' sotto test: le dipendenze non usate da quel
    # metodo (scheduler/stt/ollama) possono essere stub minimi.
    return QuantumMode(
        conn=conn,
        ollama_host="",
        brain_model_tag="",
        num_ctx=0,
        guard=FilesystemGuard(sandbox_root, service="test"),
        sandbox_root=sandbox_root,
        dreaming_scheduler=None,  # type: ignore[arg-type]
        stt=None,  # type: ignore[arg-type]
        bot_name="Babbasone",
        on_event=on_event,
    )


def test_apply_iteration_creates_two_nodes_and_an_edge(conn, sandbox_root):
    events: list[tuple[str, dict]] = []
    qm = _make_quantum(conn, sandbox_root, on_event=lambda t, p: events.append((t, p)))

    qm._apply_iteration(
        {"da": "Marco", "tipo_da": "Persona", "relazione": "riguarda", "a": "Musica", "tipo_a": "Concetto", "azione": "Marco ama la musica"}
    )

    nodes, edges = get_graph_snapshot(conn)
    labels = {n["label"] for n in nodes}
    assert {"Marco", "Musica"} <= labels
    assert len(edges) == 1
    assert any(t == "graph-updated" for t, _ in events)
    assert any(t == "quantum-insight" for t, _ in events)


def test_apply_iteration_noop_when_da_equals_a(conn, sandbox_root):
    events: list[tuple[str, dict]] = []
    qm = _make_quantum(conn, sandbox_root, on_event=lambda t, p: events.append((t, p)))

    qm._apply_iteration(
        {"da": "Marco", "tipo_da": "Persona", "relazione": "conosce", "a": "Marco", "tipo_a": "Persona", "azione": "niente di nuovo"}
    )

    _, edges = get_graph_snapshot(conn)
    assert edges == []
    assert not any(t == "graph-updated" for t, _ in events)
    # L'insight (azione) viene comunque emesso anche in un giro a vuoto.
    assert any(t == "quantum-insight" for t, _ in events)


def test_apply_iteration_ignores_invalid_relation(conn, sandbox_root):
    qm = _make_quantum(conn, sandbox_root)
    qm._apply_iteration(
        {"da": "A", "tipo_da": "Concetto", "relazione": "inventata", "a": "B", "tipo_a": "Concetto", "azione": "x"}
    )
    _, edges = get_graph_snapshot(conn)
    assert edges == []


def test_read_handoff_note_missing_file_returns_empty(guard, sandbox_root):
    assert _read_handoff_note(guard=guard, sandbox_root=sandbox_root) == ""


def test_write_then_read_handoff_note_roundtrip(guard, sandbox_root):
    _write_handoff_note("Approfondire il legame tra Marco e la musica.", guard=guard, sandbox_root=sandbox_root)
    assert _read_handoff_note(guard=guard, sandbox_root=sandbox_root) == "Approfondire il legame tra Marco e la musica."


def test_write_handoff_note_overwrites_previous(guard, sandbox_root):
    _write_handoff_note("Prima nota.", guard=guard, sandbox_root=sandbox_root)
    _write_handoff_note("Seconda nota.", guard=guard, sandbox_root=sandbox_root)
    assert _read_handoff_note(guard=guard, sandbox_root=sandbox_root) == "Seconda nota."


def test_build_iteration_prompt_lists_things_relations_and_isolated_nodes():
    nodes = [
        {"id": 1, "label": "Marco"},
        {"id": 2, "label": "Milano"},
        {"id": 3, "label": "Chitarra"},  # isolato, nessun arco
    ]
    edges = [{"source_node_id": 1, "target_node_id": 2, "edge_type": "e_avvenuto_in"}]
    prompt = _build_iteration_prompt(bot_name="Babbasone", nodes=nodes, edges=edges, handoff_note="")
    assert "Babbasone" in prompt  # istruzione personalizzata
    assert "Marco e_avvenuto_in Milano" in prompt  # collegamento esistente, formato piatto
    assert "Chitarra" in prompt  # elencata tra le cose isolate
    # Deve chiedere i campi piatti, non piu' schema annidato/temp_id.
    assert "da, tipo_da, relazione, a, tipo_a" in prompt


def test_build_iteration_prompt_includes_handoff_note_when_present():
    prompt = _build_iteration_prompt(bot_name="Babbasone", nodes=[], edges=[], handoff_note="Guarda meglio la musica.")
    assert "Guarda meglio la musica." in prompt


def test_build_iteration_prompt_omits_handoff_section_when_empty():
    prompt = _build_iteration_prompt(bot_name="Babbasone", nodes=[], edges=[], handoff_note="")
    assert "Appunto lasciato la volta scorsa" not in prompt
