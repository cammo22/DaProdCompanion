"""
Memoria semantica consolidata: scrittura (usata dal dreaming) e ricerca per
similarita' (usata dal loop di conversazione per il retrieval). La ricerca e'
in due passi (prima gli id piu' vicini dalla tabella virtuale, poi il
contenuto dalla tabella normale) invece di un JOIN unico, per non dipendere
da come sqlite-vec si comporta con MATCH/k dentro una query piu' complessa.
"""

from __future__ import annotations

import sqlite3

from companion_shared.db import write_lock

from .embeddings import serialize_embedding


def insert_semantic_memory(
    conn: sqlite3.Connection,
    *,
    summary: str,
    source_event_ids: list[int],
    embedding: list[float],
) -> int:
    with write_lock:
        cursor = conn.execute(
            "INSERT INTO semantic_memories (summary, source_event_ids) VALUES (?, ?)",
            (summary, ",".join(str(i) for i in source_event_ids)),
        )
        memory_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO semantic_memories_vec (memory_id, embedding) VALUES (?, ?)",
            (memory_id, serialize_embedding(embedding)),
        )
        conn.commit()
        return memory_id


def search_relevant_memories(
    conn: sqlite3.Connection,
    *,
    query_embedding: list[float],
    limit: int = 5,
) -> list[str]:
    matches = conn.execute(
        "SELECT memory_id FROM semantic_memories_vec WHERE embedding MATCH ? AND k = ? ORDER BY distance",
        (serialize_embedding(query_embedding), limit),
    ).fetchall()
    if not matches:
        return []
    memory_ids = [row["memory_id"] for row in matches]
    placeholders = ",".join("?" * len(memory_ids))
    rows = conn.execute(
        f"SELECT summary FROM semantic_memories WHERE id IN ({placeholders})",
        memory_ids,
    ).fetchall()
    return [row["summary"] for row in rows]
