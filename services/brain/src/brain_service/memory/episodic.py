"""
CRUD della memoria episodica grezza (tabella episodic_events). E' l'unico modulo
che scrive eventi grezzi; dreaming.consolidation legge quelli non ancora
processati e li marca come consolidati dopo averli riassunti.
"""

from __future__ import annotations

import sqlite3

from companion_shared.db import write_lock


def log_event(conn: sqlite3.Connection, *, event_type: str, content: str, source: str | None = None) -> int:
    with write_lock:
        cursor = conn.execute(
            "INSERT INTO episodic_events (event_type, content, source) VALUES (?, ?, ?)",
            (event_type, content, source),
        )
        conn.commit()
        return cursor.lastrowid


def get_recent_events(conn: sqlite3.Connection, *, limit: int = 20) -> list[sqlite3.Row]:
    cursor = conn.execute("SELECT * FROM episodic_events ORDER BY id DESC LIMIT ?", (limit,))
    return cursor.fetchall()


def get_unconsolidated_events(conn: sqlite3.Connection, *, limit: int = 200) -> list[sqlite3.Row]:
    cursor = conn.execute(
        "SELECT * FROM episodic_events WHERE consolidated = 0 ORDER BY id ASC LIMIT ?",
        (limit,),
    )
    return cursor.fetchall()


def mark_consolidated(conn: sqlite3.Connection, event_ids: list[int]) -> None:
    if not event_ids:
        return
    with write_lock:
        placeholders = ",".join("?" * len(event_ids))
        conn.execute(
            f"UPDATE episodic_events SET consolidated = 1 WHERE id IN ({placeholders})",
            event_ids,
        )
        conn.commit()
