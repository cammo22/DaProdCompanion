"""
Scheduler del dreaming: due modalita' complementari.

1. Cron-based (DREAMING_INTERVAL_CRON, di norma notturno): passata di
   consolidamento completa, pensata per girare quando la macchina e'
   presumibilmente inattiva.
2. Innescata dall'inattivita' della conversazione (notify_activity()): ogni
   scambio di chat (testo o voce) rimanda un timer breve; quando la
   conversazione si ferma per _IDLE_TRIGGER_SECONDS, parte un ciclo di
   consolidamento "a caldo". E' questo il meccanismo che fa apparire il
   pannello del grafo aggiornato "in tempo reale" agli occhi dell'utente,
   invece di restare fermo fino al prossimo giro notturno — senza pero'
   competere con la reattivita' della chat, perche' scatta solo quando la
   conversazione e' gia' in pausa (Ollama serve un solo modello alla volta,
   vedi architettura.md).

Espone anche trigger_now() per un ciclo immediato fuori programma (usato
dall'endpoint POST /dreaming/run, utile sia per i test sia per un eventuale
pulsante futuro "consolida adesso").
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime

from croniter import croniter

logger = logging.getLogger("brain")

_IDLE_TRIGGER_SECONDS = 90.0


class DreamingScheduler:
    def __init__(self, cron_expression: str, run_cycle: Callable[[], Awaitable[int]]) -> None:
        self._cron_expression = cron_expression
        self._run_cycle = run_cycle
        self._task: asyncio.Task | None = None
        self._idle_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
        if self._idle_task is not None:
            self._idle_task.cancel()

    async def trigger_now(self) -> int:
        """Esegue subito un ciclo, fuori dallo schedule. Il lock evita che un
        ciclo schedulato e uno manuale girino in contemporanea sulla stessa
        connessione DB."""
        async with self._lock:
            return await self._run_cycle()

    def notify_activity(self) -> None:
        """Da chiamare ad ogni scambio di chat riuscito (testo o voce):
        rimanda il consolidamento "a caldo" finche' la conversazione resta
        attiva, azzerando e riavviando il timer di inattivita' ad ogni
        chiamata."""
        if self._idle_task is not None:
            self._idle_task.cancel()
        self._idle_task = asyncio.create_task(self._idle_wait())

    async def _idle_wait(self) -> None:
        try:
            await asyncio.sleep(_IDLE_TRIGGER_SECONDS)
        except asyncio.CancelledError:
            return  # riavviato da un nuovo notify_activity(): questo giro non parte
        async with self._lock:
            try:
                await self._run_cycle()
            except Exception:
                logger.exception("Dreaming: ciclo innescato da inattivita' fallito")

    async def _loop(self) -> None:
        while True:
            now = datetime.now()
            next_run = croniter(self._cron_expression, now).get_next(datetime)
            sleep_seconds = max((next_run - now).total_seconds(), 1.0)
            logger.info("Dreaming: prossimo giro programmato alle %s", next_run.isoformat())
            try:
                await asyncio.sleep(sleep_seconds)
            except asyncio.CancelledError:
                return
            async with self._lock:
                try:
                    await self._run_cycle()
                except Exception:
                    logger.exception("Dreaming: ciclo schedulato fallito")
