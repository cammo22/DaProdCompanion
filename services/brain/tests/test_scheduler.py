"""
Test dello scheduler del dreaming: solo la parte innescata dalla dimensione
(check_size_trigger), che scatta subito senza timer da aspettare. Le altre
due modalita' (inattivita', cron) dipendono dal tempo reale/da croniter e
sono gia' state verificate dal vivo durante lo sviluppo.
"""

from __future__ import annotations

import asyncio

from brain_service.dreaming.scheduler import DreamingScheduler


def test_check_size_trigger_below_threshold_does_nothing():
    calls: list[int] = []

    async def run_cycle() -> int:
        calls.append(1)
        return 0

    scheduler = DreamingScheduler("0 4 * * *", run_cycle)
    scheduler.check_size_trigger(10)
    assert calls == []


def test_check_size_trigger_above_threshold_runs_cycle():
    calls: list[int] = []

    async def run_cycle() -> int:
        calls.append(1)
        return 5

    async def run() -> None:
        scheduler = DreamingScheduler("0 4 * * *", run_cycle)
        scheduler.check_size_trigger(41)
        await asyncio.sleep(0.05)  # lascia girare il task creato da check_size_trigger
        assert calls == [1]

    asyncio.run(run())


def test_check_size_trigger_cancels_pending_idle_wait():
    calls: list[int] = []

    async def run_cycle() -> int:
        calls.append(1)
        return 5

    async def run() -> None:
        scheduler = DreamingScheduler("0 4 * * *", run_cycle)
        scheduler.notify_activity()  # avvia l'attesa di 90s di inattivita'
        scheduler.check_size_trigger(41)  # deve sostituirla con un giro immediato
        await asyncio.sleep(0.05)
        assert calls == [1]  # non deve girare due volte (una per notify, una per size)

    asyncio.run(run())
