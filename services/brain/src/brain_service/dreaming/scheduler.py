"""
Scheduler del dreaming: tre modalita' complementari.

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
3. Innescata dalla dimensione (check_size_trigger()): una conversazione
   lunga e ininterrotta puo' non fermarsi mai abbastanza da far scattare il
   punto 2. Se gli eventi non ancora consolidati superano una soglia, si
   compatta subito, indipendentemente dall'inattivita' — altrimenti il
   contesto mandato al modello crescerebbe senza limite (vedi
   conversation/loop.py, che manda solo la coda recente, ma quella coda
   diventerebbe via via piu' costosa da ricostruire e piu' lontana dal
   riassunto semantico se non si consolida mai).

Espone anche trigger_now() per un ciclo immediato fuori programma (usato
dall'endpoint POST /dreaming/run, utile sia per i test sia per un eventuale
pulsante futuro "consolida adesso").

Sospensione (suppress()/unsuppress()): il trigger per dimensione scatta
SUBITO, senza aspettare una pausa — se scatta esattamente mentre l'utente
sta registrando manualmente (pulsante "registra") o sta parlando ad alta
voce, il ciclo di dreaming (una chiamata pesante a Ollama, num_predict=2048)
finisce in coda sulla STESSA istanza Ollama insieme alla prossima risposta
conversazionale, ritardandola pesantemente — e' il bug segnalato dal vivo
dall'utente ("stavo parlando e nel frattempo ha sognato"). stt_service
notifica inizio/fine di ascolto e registrazione tramite /events/voice, che
sospende/riattiva questo scheduler di conseguenza (vedi api/http.py)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime

from croniter import croniter

logger = logging.getLogger("brain")

_IDLE_TRIGGER_SECONDS = 90.0
_COMPACTION_EVENT_THRESHOLD = 40


class DreamingScheduler:
    def __init__(self, cron_expression: str, run_cycle: Callable[[], Awaitable[int]]) -> None:
        self._cron_expression = cron_expression
        self._run_cycle = run_cycle
        self._task: asyncio.Task | None = None
        self._idle_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        # Contatore, non un semplice bool: ascolto/registrazione (via
        # /events/voice) e la modalita' Quantum possono sospendere il
        # dreaming in modo indipendente e potenzialmente sovrapposto (es.
        # l'utente preme "registra" mentre Quantum e' gia' attivo). Con un
        # bool, la fine della registrazione riattiverebbe il dreaming anche
        # se Quantum lo vuole ancora sospeso — con un contatore resta
        # sospeso finche' TUTTI i sospensori non hanno chiamato unsuppress().
        self._suppress_count = 0
        self._last_dream_at: datetime | None = None
        self._next_cron_run_at: datetime | None = None

    def status(self) -> dict[str, str | None]:
        """Per il timer nel pannello grafo: ultima volta che ha sognato
        davvero (consolidated_events > 0) e prossimo giro notturno
        programmato. Non copre i trigger per inattivita'/dimensione, che non
        hanno un orario fisso da annunciare in anticipo."""
        return {
            "last_dream_at": self._last_dream_at.isoformat() if self._last_dream_at else None,
            "next_scheduled_at": self._next_cron_run_at.isoformat() if self._next_cron_run_at else None,
        }

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
        if self._idle_task is not None:
            self._idle_task.cancel()

    async def trigger_now(self) -> int:
        """Esegue subito un ciclo, fuori dallo schedule (richiesto in modo
        esplicito, es. dal pulsante nel pannello grafo): ignora la
        sospensione, a differenza dei trigger automatici sotto. Il lock evita
        che un ciclo schedulato e uno manuale girino in contemporanea sulla
        stessa connessione DB."""
        async with self._lock:
            count = await self._run_cycle()
            if count > 0:
                self._last_dream_at = datetime.now()
            return count

    def suppress(self) -> None:
        """L'utente sta ascoltando/registrando attivamente (o e' in corso la
        modalita' Quantum): nessun trigger automatico deve partire finche'
        ogni chiamante non richiama unsuppress() a sua volta, altrimenti
        rischia di mettersi in coda su Ollama insieme alla prossima risposta
        conversazionale (o al ciclo Quantum in corso) e ritardarla
        pesantemente. Incrementale: due sospensori indipendenti e sovrapposti
        (es. si preme "registra" mentre Quantum e' gia' attivo) restano
        entrambi in vigore finche' entrambi non hanno chiamato unsuppress()."""
        self._suppress_count += 1

    def unsuppress(self) -> None:
        """Controparte di suppress(): NON riattiva subito i trigger se un
        altro sospensore e' ancora attivo (contatore, non un semplice bool).
        Quando arriva davvero a zero, i trigger automatici tornano attivi dal
        prossimo scambio (non ne innesca uno subito qui, e' il normale
        notify_activity()/check_size_trigger() del prossimo /chat a farlo)."""
        self._suppress_count = max(0, self._suppress_count - 1)

    @property
    def _suppressed(self) -> bool:
        return self._suppress_count > 0

    def notify_activity(self) -> None:
        """Da chiamare ad ogni scambio di chat riuscito (testo o voce):
        rimanda il consolidamento "a caldo" finche' la conversazione resta
        attiva, azzerando e riavviando il timer di inattivita' ad ogni
        chiamata."""
        if self._idle_task is not None:
            self._idle_task.cancel()
        self._idle_task = asyncio.create_task(self._idle_wait())

    def check_size_trigger(self, unconsolidated_count: int) -> None:
        """Da chiamare subito dopo notify_activity() con il conteggio degli
        eventi non ancora consolidati: se supera la soglia, sostituisce
        l'attesa di inattivita' con un ciclo immediato."""
        if unconsolidated_count < _COMPACTION_EVENT_THRESHOLD:
            return
        if self._idle_task is not None:
            self._idle_task.cancel()
        self._idle_task = asyncio.create_task(self._run_locked_and_log("di compattazione per dimensione"))

    async def _idle_wait(self) -> None:
        try:
            await asyncio.sleep(_IDLE_TRIGGER_SECONDS)
        except asyncio.CancelledError:
            return  # riavviato da un nuovo notify_activity(): questo giro non parte
        await self._run_locked_and_log("innescato da inattivita'")

    async def _run_locked_and_log(self, label: str) -> None:
        if self._suppressed:
            logger.info("Dreaming: ciclo %s rimandato (ascolto/registrazione in corso)", label)
            return
        async with self._lock:
            try:
                count = await self._run_cycle()
                if count > 0:
                    self._last_dream_at = datetime.now()
            except Exception:
                logger.exception("Dreaming: ciclo %s fallito", label)

    async def _loop(self) -> None:
        while True:
            now = datetime.now()
            next_run = croniter(self._cron_expression, now).get_next(datetime)
            self._next_cron_run_at = next_run
            sleep_seconds = max((next_run - now).total_seconds(), 1.0)
            logger.info("Dreaming: prossimo giro programmato alle %s", next_run.isoformat())
            try:
                await asyncio.sleep(sleep_seconds)
            except asyncio.CancelledError:
                return
            await self._run_locked_and_log("schedulato")
