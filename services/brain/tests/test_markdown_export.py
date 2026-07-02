"""Test della formattazione markdown (pura, niente filesystem/DB coinvolti,
tranne per append_identity_reflection che usa FilesystemGuard reale su
tmp_path, stesso pattern di shared/tests/test_fs_guard.py)."""

from __future__ import annotations

import pytest
from companion_shared.sandbox import FilesystemGuard

from brain_service.dreaming.markdown_export import _entity_markdown, _slugify, append_identity_reflection


@pytest.fixture
def sandbox_root(tmp_path):
    return tmp_path / "sandbox"


@pytest.fixture
def guard(sandbox_root):
    return FilesystemGuard(sandbox_root, service="test")


def test_slugify_basic():
    assert _slugify("Marco Rossi") == "marco-rossi"


def test_slugify_strips_accents_and_punctuation():
    assert _slugify("Sviluppo software!") == "sviluppo-software"


def test_slugify_empty_label_has_fallback():
    assert _slugify("   ") == "senza-nome"


def test_entity_markdown_with_no_connections():
    node = {"id": 1, "node_type": "Persona", "label": "Marco", "created_at": "2026-07-01", "updated_at": "2026-07-02", "metadata": None}
    content = _entity_markdown(node, [], [], {1: node})
    assert "# Marco" in content
    assert 'type: "Persona"' in content
    assert "Nessuna connessione ancora." in content


def test_entity_markdown_has_yaml_frontmatter():
    node = {
        "id": 1,
        "node_type": "Persona",
        "label": "Marco",
        "created_at": "2026-07-01T10:00:00",
        "updated_at": "2026-07-02T11:00:00",
        "metadata": '{"tags": ["amico", "sviluppatore"], "sources": ["Sogno del 2026-07-02"], "confidence": 0.8}',
    }
    content = _entity_markdown(node, [], [], {1: node})
    assert content.startswith("---\n")
    assert 'title: "Marco"' in content
    assert "created: \"2026-07-01T10:00:00\"" in content
    assert 'tags: ["amico", "sviluppatore"]' in content
    assert "confidence: 0.8" in content


def test_entity_markdown_with_outgoing_and_incoming():
    marco = {"id": 1, "node_type": "Persona", "label": "Marco", "created_at": None, "updated_at": None, "metadata": None}
    milano = {"id": 2, "node_type": "Luogo", "label": "Milano", "created_at": None, "updated_at": None, "metadata": None}
    node_by_id = {1: marco, 2: milano}

    outgoing = [{"source_node_id": 1, "target_node_id": 2, "edge_type": "e_avvenuto_in"}]
    incoming = [{"source_node_id": 2, "target_node_id": 1, "edge_type": "conosce"}]

    content = _entity_markdown(marco, outgoing, incoming, node_by_id)
    assert "e' avvenuto in → [[Milano]]" in content
    assert "[[Milano]] → conosce" in content


def test_append_identity_reflection_creates_file_with_header(guard, sandbox_root):
    append_identity_reflection("Mi piace scherzare con l'utente.", bot_name="Babbasone", guard=guard, sandbox_root=sandbox_root)
    content = (sandbox_root / "chi-sono.md").read_text(encoding="utf-8")
    assert "# Chi sono io, Babbasone" in content
    assert "Mi piace scherzare con l'utente." in content


def test_append_identity_reflection_accumulates_over_calls(guard, sandbox_root):
    append_identity_reflection("Prima riflessione.", bot_name="Babbasone", guard=guard, sandbox_root=sandbox_root)
    append_identity_reflection("Seconda riflessione.", bot_name="Babbasone", guard=guard, sandbox_root=sandbox_root)
    content = (sandbox_root / "chi-sono.md").read_text(encoding="utf-8")
    assert "Prima riflessione." in content
    assert "Seconda riflessione." in content
    assert content.count("# Chi sono io, Babbasone") == 1  # l'header non si ripete
