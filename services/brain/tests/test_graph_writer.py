"""
Test di find_or_create_node/edge con un DB SQLite reale (migrazioni vere,
stesso pattern di test_admin_reset.py): la parte interessante da verificare
e' che ritoccare lo stesso nodo in cicli di dreaming diversi accumuli tag e
fonti invece di sovrascriverli, dato che il frontmatter markdown si basa su
questo per mostrare tutte le fonti che hanno citato un'entita' nel tempo.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from companion_shared.db import open_connection

from brain_service.graph.writer import find_or_create_edge, find_or_create_node


@pytest.fixture
def conn(tmp_path: Path):
    connection = open_connection(tmp_path / "test.db")
    yield connection
    connection.close()


def test_create_node_stores_tags_confidence_and_source(conn):
    node_id = find_or_create_node(
        conn, node_type="Persona", label="Marco", tags=["amico"], confidence=0.9, source="Sogno del 2026-07-02"
    )
    row = conn.execute("SELECT metadata, updated_at FROM graph_nodes WHERE id = ?", (node_id,)).fetchone()
    metadata = json.loads(row["metadata"])
    assert metadata["tags"] == ["amico"]
    assert metadata["confidence"] == 0.9
    assert metadata["sources"] == ["Sogno del 2026-07-02"]
    assert row["updated_at"] is not None


def test_reusing_node_merges_tags_and_appends_sources(conn):
    node_id = find_or_create_node(
        conn, node_type="Persona", label="Marco", tags=["amico"], confidence=0.6, source="Sogno del 2026-07-01"
    )
    same_id = find_or_create_node(
        conn, node_type="Persona", label="marco", tags=["napoli"], confidence=0.9, source="Sogno del 2026-07-02"
    )
    assert same_id == node_id

    row = conn.execute("SELECT metadata FROM graph_nodes WHERE id = ?", (node_id,)).fetchone()
    metadata = json.loads(row["metadata"])
    assert set(metadata["tags"]) == {"amico", "napoli"}
    assert metadata["sources"] == ["Sogno del 2026-07-01", "Sogno del 2026-07-02"]
    assert metadata["confidence"] == 0.9  # l'ultimo valore vince


def test_reusing_node_without_new_source_keeps_existing_metadata(conn):
    node_id = find_or_create_node(conn, node_type="Persona", label="Marco", tags=["amico"], confidence=0.6, source="Sogno del 2026-07-01")
    find_or_create_node(conn, node_type="Persona", label="Marco", tags=[], confidence=None, source=None)

    row = conn.execute("SELECT metadata FROM graph_nodes WHERE id = ?", (node_id,)).fetchone()
    metadata = json.loads(row["metadata"])
    assert metadata["tags"] == ["amico"]
    assert metadata["confidence"] == 0.6
    assert metadata["sources"] == ["Sogno del 2026-07-01"]


def test_find_or_create_edge_deduplicates(conn):
    a = find_or_create_node(conn, node_type="Persona", label="A")
    b = find_or_create_node(conn, node_type="Persona", label="B")
    edge_id = find_or_create_edge(conn, source_node_id=a, target_node_id=b, edge_type="conosce")
    same_edge_id = find_or_create_edge(conn, source_node_id=a, target_node_id=b, edge_type="conosce")
    assert edge_id == same_edge_id
