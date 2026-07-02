"""
Apertura della connessione SQLite condivisa: modalita' WAL, estensione sqlite-vec
caricata, migrazioni applicate. Punto unico di accesso al file companion.db, che
vive sotto SANDBOX_ROOT (il percorso arriva gia' risolto dal chiamante tramite
Settings.resolved_db_path() — e' un percorso interno fisso, non una richiesta
arbitraria, quindi non passa per fs_guard.resolve_and_check()).
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path

import sqlite_vec

from . import schema

# Lock applicativo attorno alle scritture: la connessione e' condivisa da piu'
# task asyncio all'interno dello stesso processo (brain_service), e sqlite3 non
# garantisce da solo la serializzazione delle scritture concorrenti.
write_lock = threading.Lock()


def open_connection(db_path: Path, *, logger: logging.Logger | None = None) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA foreign_keys=ON;")

    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

    schema.apply_migrations(conn, logger=logger)

    return conn
