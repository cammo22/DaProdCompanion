"""
Reset completo della memoria del companion: svuota le tabelle di memoria
episodica, semantica e del grafo di conoscenza, E il vault markdown esportato
su disco (entita/, sogni/, chi-sono.md, quantum_handoff.md) — altrimenti dopo
un reset il grafo su disco continuerebbe a mostrare le vecchie entita' anche
se il DB e' vuoto, dato che l'export markdown vive fuori da SQLite (vedi
dreaming/markdown_export.py). Non tocca sandbox_access_log (audit trail
tecnico del wrapper di sandboxing) ne' schema_migrations (bookkeeping
interno): non sono "memoria" del companion, sono infrastruttura.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from companion_shared.db import write_lock
from companion_shared.sandbox import FilesystemGuard

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

_MARKDOWN_PATHS_TO_CLEAR = [
    Path("memoria") / "entita",
    Path("memoria") / "sogni",
    Path("memoria") / "quantum_handoff.md",
    Path("chi-sono.md"),
]


def reset_all_memory(conn: sqlite3.Connection, *, guard: FilesystemGuard | None = None, sandbox_root: Path | None = None) -> None:
    with write_lock:
        for table in _TABLES_TO_CLEAR:
            conn.execute(f"DELETE FROM {table}")
        conn.commit()

    if guard is not None and sandbox_root is not None:
        for relative_path in _MARKDOWN_PATHS_TO_CLEAR:
            guard.delete_sandboxed(sandbox_root / relative_path, purpose="reset completo della memoria")
