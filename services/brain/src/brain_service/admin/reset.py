"""
Reset completo della memoria del companion: svuota le tabelle di memoria
episodica, semantica e del grafo di conoscenza. Non tocca sandbox_access_log
(audit trail tecnico del wrapper di sandboxing) ne' schema_migrations
(bookkeeping interno): non sono "memoria" del companion, sono infrastruttura.
"""

from __future__ import annotations

import sqlite3

from companion_shared.db import write_lock

# Ordine importante: le tabelle con FOREIGN KEY vanno svuotate prima delle
# tabelle a cui puntano (PRAGMA foreign_keys=ON e' attivo, vedi db/connection.py),
# altrimenti sqlite3.IntegrityError. face_embeddings/known_people sono vuote
# finche' la Fase Webcam non esiste, ma l'ordine e' gia' corretto per allora.
_TABLES_TO_CLEAR = [
    "face_embeddings",  # -> known_people
    "known_people",  # -> graph_nodes
    "graph_edges",  # -> graph_nodes
    "graph_nodes",
    "semantic_memories_vec",
    "semantic_memories",
    "episodic_events",
]


def reset_all_memory(conn: sqlite3.Connection) -> None:
    with write_lock:
        for table in _TABLES_TO_CLEAR:
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
