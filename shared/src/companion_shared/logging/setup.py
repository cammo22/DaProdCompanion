"""
Configurazione del logging condivisa da tutti i servizi Python: console + file
sotto <SANDBOX_ROOT>/logs/<service>.log. log_dir arriva gia' risolto dal chiamante
(derivato da Settings.resolved_log_dir(), quindi gia' garantito dentro la sandbox):
questo modulo non passa per fs_guard perche' non gestisce percorsi arbitrari, solo
il percorso interno fisso dei log applicativi.
"""

from __future__ import annotations

import logging
from pathlib import Path


def setup_logging(*, service: str, log_dir: Path, level: str = "INFO") -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(service)
    logger.setLevel(level)

    if logger.handlers:
        # Evita handler duplicati se la funzione viene richiamata piu' volte
        # (es. durante i reload di uvicorn in sviluppo).
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_dir / f"{service}.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
