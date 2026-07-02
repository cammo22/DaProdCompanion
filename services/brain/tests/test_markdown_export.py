"""Test della formattazione markdown (pura, niente filesystem/DB coinvolti)."""

from __future__ import annotations

from brain_service.dreaming.markdown_export import _entity_markdown, _slugify


def test_slugify_basic():
    assert _slugify("Marco Rossi") == "marco-rossi"


def test_slugify_strips_accents_and_punctuation():
    assert _slugify("Sviluppo software!") == "sviluppo-software"


def test_slugify_empty_label_has_fallback():
    assert _slugify("   ") == "senza-nome"


def test_entity_markdown_with_no_connections():
    node = {"id": 1, "node_type": "Persona", "label": "Marco"}
    content = _entity_markdown(node, [], [], {1: node})
    assert "# Marco" in content
    assert "**Tipo**: Persona" in content
    assert "Nessuna connessione ancora." in content


def test_entity_markdown_with_outgoing_and_incoming():
    marco = {"id": 1, "node_type": "Persona", "label": "Marco"}
    milano = {"id": 2, "node_type": "Luogo", "label": "Milano"}
    node_by_id = {1: marco, 2: milano}

    outgoing = [{"source_node_id": 1, "target_node_id": 2, "edge_type": "e_avvenuto_in"}]
    incoming = [{"source_node_id": 2, "target_node_id": 1, "edge_type": "conosce"}]

    content = _entity_markdown(marco, outgoing, incoming, node_by_id)
    assert "e' avvenuto in → [[Milano]]" in content
    assert "[[Milano]] → conosce" in content
