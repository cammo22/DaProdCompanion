"""
Test del reset completo della memoria: soprattutto una rete di sicurezza
contro l'ordine di cancellazione rispetto ai vincoli FOREIGN KEY (regressione
reale osservata: cancellare graph_nodes prima di graph_edges causa
sqlite3.IntegrityError, dato che PRAGMA foreign_keys=ON e' attivo).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from companion_shared.db import open_connection

from companion_shared.sandbox import FilesystemGuard

from brain_service.admin.reset import reset_all_memory
from brain_service.memory.embeddings import serialize_embedding

_TABLES = [
    "episodic_events",
    "semantic_memories",
    "semantic_memories_vec",
    "graph_nodes",
    "graph_edges",
    "known_people",
    "face_embeddings",
]


@pytest.fixture
def conn(tmp_path: Path):
    connection = open_connection(tmp_path / "test.db")
    yield connection
    connection.close()


def _count(conn, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_reset_clears_all_memory_tables_without_fk_violation(conn):
    # Popola dati che rispettano le FK: nodo -> arco, persona -> volto.
    conn.execute("INSERT INTO episodic_events (event_type, content) VALUES ('user_message', 'ciao')")
    memory_id = conn.execute(
        "INSERT INTO semantic_memories (summary, source_event_ids) VALUES ('riassunto', '1')"
    ).lastrowid
    conn.execute(
        "INSERT INTO semantic_memories_vec (memory_id, embedding) VALUES (?, ?)",
        (memory_id, serialize_embedding([0.1] * 768)),
    )
    node_a = conn.execute("INSERT INTO graph_nodes (node_type, label) VALUES ('Persona', 'A')").lastrowid
    node_b = conn.execute("INSERT INTO graph_nodes (node_type, label) VALUES ('Persona', 'B')").lastrowid
    conn.execute(
        "INSERT INTO graph_edges (source_node_id, target_node_id, edge_type) VALUES (?, ?, 'conosce')",
        (node_a, node_b),
    )
    person = conn.execute(
        "INSERT INTO known_people (display_name, graph_node_id) VALUES ('A', ?)", (node_a,)
    ).lastrowid
    conn.execute(
        "INSERT INTO face_embeddings (person_id, embedding) VALUES (?, ?)", (person, b"\x00\x01")
    )
    conn.commit()

    for table in _TABLES:
        assert _count(conn, table) > 0, f"setup non ha popolato {table}"

    reset_all_memory(conn)  # non deve sollevare IntegrityError

    for table in _TABLES:
        assert _count(conn, table) == 0, f"{table} non vuota dopo il reset"


def test_reset_on_already_empty_db_is_a_no_op(conn):
    reset_all_memory(conn)  # non deve sollevare eccezioni su un DB gia' vuoto
    for table in _TABLES:
        assert _count(conn, table) == 0


def test_reset_also_clears_the_markdown_vault(conn, tmp_path):
    sandbox_root = tmp_path / "sandbox"
    guard = FilesystemGuard(sandbox_root, service="test")

    with guard.open_sandboxed(sandbox_root / "memoria" / "entita" / "marco.md", "w") as f:
        f.write("# Marco")
    with guard.open_sandboxed(sandbox_root / "memoria" / "sogni" / "2026-01-01.md", "w") as f:
        f.write("# Sogno")
    with guard.open_sandboxed(sandbox_root / "memoria" / "quantum_handoff.md", "w") as f:
        f.write("nota")
    with guard.open_sandboxed(sandbox_root / "chi-sono.md", "w") as f:
        f.write("# Chi sono")

    reset_all_memory(conn, guard=guard, sandbox_root=sandbox_root)

    assert not (sandbox_root / "memoria" / "entita").exists()
    assert not (sandbox_root / "memoria" / "sogni").exists()
    assert not (sandbox_root / "memoria" / "quantum_handoff.md").exists()
    assert not (sandbox_root / "chi-sono.md").exists()


def test_reset_without_guard_skips_markdown_cleanup(conn):
    reset_all_memory(conn)  # guard/sandbox_root non forniti: non deve sollevare eccezioni
