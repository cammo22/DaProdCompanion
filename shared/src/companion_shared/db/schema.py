"""
Apparato minimo di migrazione dello schema SQLite.

Le tabelle sono definite negli script .sql sotto migrations/, applicati in ordine
alfabetico e tracciati nella tabella schema_migrations. Questo modulo si limita ad
eseguirli: la definizione delle tabelle vive nei file .sql, non qui.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

_BOOTSTRAP_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL UNIQUE,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def apply_migrations(conn: sqlite3.Connection, *, logger: logging.Logger | None = None) -> None:
    conn.executescript(_BOOTSTRAP_SQL)

    applied = {row[0] for row in conn.execute("SELECT filename FROM schema_migrations")}

    for migration_file in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        if migration_file.name in applied:
            continue
        sql = migration_file.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.execute("INSERT INTO schema_migrations (filename) VALUES (?)", (migration_file.name,))
        conn.commit()
        if logger:
            logger.info("Migrazione applicata: %s", migration_file.name)
