"""
Test della parte pura/filesystem di Quantum mode (niente chiamate di rete
reali a Ollama, coerente con la filosofia di test del progetto: il ciclo
vero e proprio, che dipende da httpx/Ollama, si verifica dal vivo come il
resto del loop di conversazione)."""

from __future__ import annotations

from pathlib import Path

import pytest
from companion_shared.sandbox import FilesystemGuard

from brain_service.quantum.mode import _build_iteration_prompt, _read_handoff_note, _write_handoff_note


@pytest.fixture
def sandbox_root(tmp_path):
    return tmp_path / "sandbox"


@pytest.fixture
def guard(sandbox_root):
    return FilesystemGuard(sandbox_root, service="test")


def test_read_handoff_note_missing_file_returns_empty(guard, sandbox_root):
    assert _read_handoff_note(guard=guard, sandbox_root=sandbox_root) == ""


def test_write_then_read_handoff_note_roundtrip(guard, sandbox_root):
    _write_handoff_note("Approfondire il legame tra Marco e la musica.", guard=guard, sandbox_root=sandbox_root)
    assert _read_handoff_note(guard=guard, sandbox_root=sandbox_root) == "Approfondire il legame tra Marco e la musica."


def test_write_handoff_note_overwrites_previous(guard, sandbox_root):
    _write_handoff_note("Prima nota.", guard=guard, sandbox_root=sandbox_root)
    _write_handoff_note("Seconda nota.", guard=guard, sandbox_root=sandbox_root)
    assert _read_handoff_note(guard=guard, sandbox_root=sandbox_root) == "Seconda nota."


def test_build_iteration_prompt_lists_relations_and_isolated_nodes():
    nodes = [
        {"id": 1, "label": "Marco"},
        {"id": 2, "label": "Milano"},
        {"id": 3, "label": "Chitarra"},  # isolato, nessun arco
    ]
    edges = [{"source_node_id": 1, "target_node_id": 2, "edge_type": "e_avvenuto_in"}]
    prompt = _build_iteration_prompt(nodes=nodes, edges=edges, handoff_note="")
    assert "Marco --e_avvenuto_in--> Milano" in prompt
    assert "Chitarra" in prompt  # elencata tra le entita' isolate


def test_build_iteration_prompt_includes_handoff_note_when_present():
    prompt = _build_iteration_prompt(nodes=[], edges=[], handoff_note="Guarda meglio la musica.")
    assert "Guarda meglio la musica." in prompt


def test_build_iteration_prompt_omits_handoff_section_when_empty():
    prompt = _build_iteration_prompt(nodes=[], edges=[], handoff_note="")
    assert "Nota lasciata dall'ultimo ciclo" not in prompt
