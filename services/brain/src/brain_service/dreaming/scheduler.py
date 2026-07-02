"""
Scheduler cron-based del dreaming: calcola il prossimo orario da
DREAMING_INTERVAL_CRON, attende fino ad allora, esegue un ciclo e ricomincia.
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


class DreamingScheduler:
    def __init__(self, cron_expression: str, run_cycle: Callable[[], Awaitable[int]]) -> None:
        self._cron_expression = cron_expression
        self._run_cycle = run_cycle
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()

    async def trigger_now(self) -> int:
        """Esegue subito un ciclo, fuori dallo schedule. Il lock evita che un
        ciclo schedulato e uno manuale girino in contemporanea sulla stessa
        connessione DB."""
        async with self._lock:
            return await self._run_cycle()

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
