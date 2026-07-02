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


def test_suppressed_size_trigger_does_not_run():
    # Il bug reale segnalato dal vivo: il trigger per dimensione scatta senza
    # aspettare una pausa, quindi puo' scattare mentre l'utente sta
    # registrando/parlando e mettersi in coda su Ollama insieme alla
    # risposta imminente. suppress() deve impedirlo del tutto.
    calls: list[int] = []

    async def run_cycle() -> int:
        calls.append(1)
        return 5

    async def run() -> None:
        scheduler = DreamingScheduler("0 4 * * *", run_cycle)
        scheduler.suppress()
        scheduler.check_size_trigger(41)
        await asyncio.sleep(0.05)
        assert calls == []

    asyncio.run(run())


def test_unsuppress_allows_the_next_trigger_to_run():
    calls: list[int] = []

    async def run_cycle() -> int:
        calls.append(1)
        return 5

    async def run() -> None:
        scheduler = DreamingScheduler("0 4 * * *", run_cycle)
        scheduler.suppress()
        scheduler.check_size_trigger(41)
        await asyncio.sleep(0.05)
        assert calls == []  # sospeso: non e' partito

        scheduler.unsuppress()
        scheduler.check_size_trigger(41)  # il prossimo scambio lo rivaluta
        await asyncio.sleep(0.05)
        assert calls == [1]

    asyncio.run(run())


def test_status_starts_empty():
    async def run_cycle() -> int:
        return 0

    scheduler = DreamingScheduler("0 4 * * *", run_cycle)
    status = scheduler.status()
    assert status == {"last_dream_at": None, "next_scheduled_at": None}


def test_status_records_last_dream_only_when_something_consolidated():
    async def run_cycle_nothing() -> int:
        return 0

    async def run() -> None:
        scheduler = DreamingScheduler("0 4 * * *", run_cycle_nothing)
        await scheduler.trigger_now()
        assert scheduler.status()["last_dream_at"] is None  # niente consolidato, niente timestamp

    asyncio.run(run())


def test_status_records_last_dream_when_something_consolidated():
    async def run_cycle_something() -> int:
        return 3

    async def run() -> None:
        scheduler = DreamingScheduler("0 4 * * *", run_cycle_something)
        await scheduler.trigger_now()
        assert scheduler.status()["last_dream_at"] is not None

    asyncio.run(run())


def test_trigger_now_ignores_suppression():
    # Richiesta esplicita dall'utente (es. pulsante "aggiorna adesso" nel
    # pannello grafo): deve funzionare anche durante ascolto/registrazione.
    calls: list[int] = []

    async def run_cycle() -> int:
        calls.append(1)
        return 5

    async def run() -> None:
        scheduler = DreamingScheduler("0 4 * * *", run_cycle)
        scheduler.suppress()
        result = await scheduler.trigger_now()
        assert result == 5
        assert calls == [1]

    asyncio.run(run())
