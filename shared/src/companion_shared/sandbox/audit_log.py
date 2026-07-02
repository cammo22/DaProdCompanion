"""
Registro di audit per il wrapper di sandboxing filesystem.

Ogni tentativo di accesso (consentito o negato) viene scritto come riga JSON in
<SANDBOX_ROOT>/logs/sandbox_access_<service>.log (un file per servizio, per evitare
interleaving di scritture concorrenti tra processi diversi). Se una connessione DB
e' stata registrata con attach_db_sink() (solo brain_service lo fa, essendo l'unico
scrittore ammesso sul database condiviso), la stessa voce viene anche inserita nella
tabella sandbox_access_log per renderla interrogabile.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

_db_sink: sqlite3.Connection | None = None
_lock = threading.Lock()


def attach_db_sink(connection: sqlite3.Connection) -> None:
    """Registra una connessione DB per rispecchiare i log anche nella tabella sandbox_access_log.
    Va chiamata solo dal processo che possiede la connessione in scrittura (brain_service)."""
    global _db_sink
    with _lock:
        _db_sink = connection


def detach_db_sink() -> None:
    """Rimuove il sink DB registrato (usato allo shutdown e nei test, per non tenere
    riferimenti a connessioni chiuse)."""
    global _db_sink
    with _lock:
        _db_sink = None


def record(*, log_dir: Path, service: str, requested_path: str, allowed: bool, reason: str = "") -> None:
    """Registra un tentativo di accesso. Non solleva mai eccezioni verso il chiamante:
    un errore di logging non deve mai bloccare l'esito gia' deciso dal fs_guard."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": service,
        "requested_path": requested_path,
        "allowed": allowed,
        "reason": reason,
    }

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"sandbox_access_{service}.log"
        with _lock, log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(f"[sandbox.audit_log] impossibile scrivere il log su file: {exc}", file=sys.stderr)

    if _db_sink is not None:
        try:
            with _lock:
                _db_sink.execute(
                    "INSERT INTO sandbox_access_log (timestamp, service, requested_path, allowed, reason) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (entry["timestamp"], service, requested_path, int(allowed), reason),
                )
                _db_sink.commit()
        except sqlite3.Error as exc:
            print(f"[sandbox.audit_log] impossibile scrivere il log su DB: {exc}", file=sys.stderr)
