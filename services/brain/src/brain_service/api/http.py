"""
API REST di brain_service: /health per il readiness check del supervisor Electron,
/chat per il ciclo di conversazione (LLM + sintesi vocale), /dreaming/run per un
consolidamento immediato fuori programma, /graph/snapshot per lo stato corrente
del grafo, /shutdown per lo spegnimento pulito richiesto dal supervisore. Il
WebSocket /ws inoltra eventi push (dreaming-started/finished, graph-updated)
che Electron non puo' ottenere restando in attesa di una risposta HTTP, perche'
brain li genera di sua iniziativa (schedulati) e non su richiesta.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from companion_shared.config import Settings, ensure_bot_name, load_settings
from companion_shared.db import open_connection
from companion_shared.logging import setup_logging
from companion_shared.sandbox import FilesystemGuard, audit_log
from fastapi import FastAPI, HTTPException

from ..admin.reset import reset_all_memory
from ..conversation.loop import handle_user_message
from ..conversation.ollama_client import OllamaClient
from ..conversation.stt_client import SttClient
from ..conversation.tts_client import TtsClient
from ..dreaming.consolidation import run_dreaming_cycle
from ..dreaming.scheduler import DreamingScheduler
from ..events.bus import EventBus
from ..graph.snapshot import get_graph_snapshot
from ..memory import episodic
from ..quantum.mode import QuantumMode
from .schemas import (
    ChatRequest,
    ChatResponse,
    ConversationHistoryResponse,
    ConversationTurnOut,
    DreamingRunResponse,
    DreamingStatusResponse,
    GraphSnapshotResponse,
    HealthResponse,
    PartialTranscriptRequest,
    QuantumStatusResponse,
    VoiceEventRequest,
)
from .ws import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ensure_bot_name qui e' una rete di sicurezza (il caso normale e' che
    # __main__.py l'abbia gia' risolto prima di avviare uvicorn): se BOT_NAME e'
    # gia' impostato non fa nulla, altrimenti chiede da terminale anche in questo
    # percorso di avvio alternativo (es. uvicorn lanciato direttamente).
    settings = ensure_bot_name(load_settings())
    sandbox_root = settings.resolved_sandbox_root()
    log_dir = settings.resolved_log_dir()

    app_logger = setup_logging(service="brain", log_dir=log_dir, level=settings.log_level)

    guard = FilesystemGuard(sandbox_root, service="brain", log_dir=log_dir)
    db_path = guard.resolve_and_check(settings.resolved_db_path(), purpose="apertura database applicativo")

    conn = open_connection(db_path, logger=app_logger)
    audit_log.attach_db_sink(conn)

    ollama = OllamaClient(settings.ollama_host)
    tts = TtsClient(f"http://127.0.0.1:{settings.tts_http_port}")
    stt = SttClient(f"http://127.0.0.1:{settings.stt_http_port}")
    event_bus = EventBus()

    async def _dreaming_cycle() -> int:
        return await run_dreaming_cycle(
            conn=conn,
            ollama_host=settings.ollama_host,
            brain_model_tag=settings.brain_model_tag,
            embedding_model_tag=settings.embedding_model_tag,
            num_ctx=settings.brain_model_num_ctx,
            guard=guard,
            sandbox_root=sandbox_root,
            bot_name=settings.bot_name,
            tts=tts,
            on_event=event_bus.publish,
        )

    dreaming_scheduler = DreamingScheduler(settings.dreaming_interval_cron, _dreaming_cycle)
    dreaming_scheduler.start()

    quantum_mode = QuantumMode(
        conn=conn,
        ollama_host=settings.ollama_host,
        brain_model_tag=settings.brain_model_tag,
        num_ctx=settings.brain_model_num_ctx,
        guard=guard,
        sandbox_root=sandbox_root,
        dreaming_scheduler=dreaming_scheduler,
        stt=stt,
        on_event=event_bus.publish,
    )

    app.state.settings = settings
    app.state.conn = conn
    app.state.ollama = ollama
    app.state.tts = tts
    app.state.stt = stt
    app.state.guard = guard
    app.state.logger = app_logger
    app.state.dreaming_scheduler = dreaming_scheduler
    app.state.quantum_mode = quantum_mode
    app.state.event_bus = event_bus

    app_logger.info("brain_service pronto: bot_name=%s sandbox_root=%s", settings.bot_name, sandbox_root)

    yield

    await quantum_mode.stop()
    dreaming_scheduler.stop()
    await ollama.aclose()
    await tts.aclose()
    await stt.aclose()
    audit_log.detach_db_sink()
    conn.close()


app = FastAPI(title="brain_service", lifespan=lifespan)
app.include_router(ws_router)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings: Settings = app.state.settings
    return HealthResponse(status="ok", bot_name=settings.bot_name)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Il messaggio non puo' essere vuoto")

    quantum_mode: QuantumMode = app.state.quantum_mode
    if quantum_mode.is_active():
        # Mentre la modalita' Quantum e' attiva il companion "non fa altro":
        # niente chiamata al modello, una risposta di cortesia fissa e basta
        # (il microfono e' gia' mutato lato stt, ma la chat testuale resta
        # comunque raggiungibile, quindi va gestita anche qui).
        return ChatResponse(reply="Sto rielaborando i miei ricordi, un attimo di pazienza...", used_memory=False)

    # La chat testuale riceve gia' la risposta nel valore HTTP di ritorno
    # (Electron aggiorna l'avatar da li'). Chi parla non e' in ascolto di
    # nessuna risposta HTTP: e' stt_service, fire-and-forget, che ha gia'
    # chiuso la sua richiesta. Senza questi due eventi sul bus, la risposta
    # generata (testo + audio) non arriverebbe mai all'avatar.
    is_voice = request.source == "voice"
    if is_voice:
        app.state.event_bus.publish("voice-processing", {})

    try:
        result = await handle_user_message(
            user_message=request.message,
            settings=app.state.settings,
            conn=app.state.conn,
            ollama=app.state.ollama,
            tts=app.state.tts,
        )
    except Exception:
        # Senza questo, un errore (es. Ollama irraggiungibile) lascerebbe
        # l'avatar bloccato sullo stato "thinking" per sempre: la chat
        # testuale se ne accorge dal fallimento della chiamata HTTP stessa
        # (vedi chat-handlers.ts), ma stt_service non aspetta la risposta.
        if is_voice:
            app.state.event_bus.publish("voice-processing-failed", {})
        raise

    # Rimanda il consolidamento "a caldo" (vedi DreamingScheduler.notify_activity):
    # cosi' il grafo/la memoria semantica si aggiornano a ridosso della
    # conversazione reale una volta che si ferma, non solo al giro notturno.
    scheduler: DreamingScheduler = app.state.dreaming_scheduler
    scheduler.notify_activity()
    # Una conversazione lunga e ininterrotta potrebbe non fermarsi mai
    # abbastanza da far scattare l'inattivita': se gli eventi non consolidati
    # sono troppi, si compatta comunque subito (vedi scheduler.py).
    unconsolidated_count = len(episodic.get_unconsolidated_events(app.state.conn, limit=200))
    scheduler.check_size_trigger(unconsolidated_count)

    if is_voice:
        app.state.event_bus.publish(
            "voice-reply",
            {
                "user_message": request.message,
                "reply": result.reply,
                "audio_path": result.audio_path,
                "duration_seconds": result.duration_seconds,
                "used_memory": result.used_memory,
            },
        )

    return ChatResponse(
        reply=result.reply,
        audio_path=result.audio_path,
        duration_seconds=result.duration_seconds,
        used_memory=result.used_memory,
    )


@app.post("/events/voice")
async def events_voice(request: VoiceEventRequest) -> dict[str, str]:
    """Relay verso Electron per eventi originati da stt_service (stato del
    microfono) sull'unico canale WS esistente: per design solo brain parla
    con Electron in push (vedi architettura.md), stt non apre un suo canale.

    Ascolto/registrazione attivi sospendono anche il dreaming automatico
    (vedi DreamingScheduler.suppress): un ciclo di dreaming che scattasse
    proprio mentre l'utente sta parlando o registrando si metterebbe in coda
    su Ollama insieme alla risposta imminente e la ritarderebbe pesantemente."""
    app.state.event_bus.publish(request.type, {})
    scheduler: DreamingScheduler = app.state.dreaming_scheduler
    if request.type in ("listening-started", "recording-started"):
        scheduler.suppress()
    elif request.type in ("listening-finished", "recording-finished"):
        scheduler.unsuppress()
    return {"status": "ok"}


@app.post("/events/partial-transcript")
async def events_partial_transcript(request: PartialTranscriptRequest) -> dict[str, str]:
    """Relay verso Electron dell'anteprima del parlato (vedi
    VoicePipeline.on_partial_transcript): stesso motivo di /events/voice,
    solo brain parla con Electron in push. Testo vuoto = 'anteprima
    cancellata', non un errore."""
    app.state.event_bus.publish("partial-transcript", {"text": request.text})
    return {"status": "ok"}


@app.post("/dreaming/run", response_model=DreamingRunResponse)
async def dreaming_run() -> DreamingRunResponse:
    """Consolidamento immediato, fuori dallo schedule cron: utile per i test
    e per il pulsante 'aggiorna adesso' nel pannello grafo."""
    scheduler: DreamingScheduler = app.state.dreaming_scheduler
    consolidated = await scheduler.trigger_now()
    return DreamingRunResponse(consolidated_events=consolidated)


@app.get("/dreaming/status", response_model=DreamingStatusResponse)
async def dreaming_status() -> DreamingStatusResponse:
    """Per il timer nel pannello grafo: ultima volta che ha sognato davvero
    e prossimo giro notturno programmato."""
    scheduler: DreamingScheduler = app.state.dreaming_scheduler
    status = scheduler.status()
    return DreamingStatusResponse(**status)


@app.post("/quantum/start", response_model=QuantumStatusResponse)
async def quantum_start() -> QuantumStatusResponse:
    quantum_mode: QuantumMode = app.state.quantum_mode
    await quantum_mode.start()
    return QuantumStatusResponse(**quantum_mode.status())


@app.post("/quantum/stop", response_model=QuantumStatusResponse)
async def quantum_stop() -> QuantumStatusResponse:
    quantum_mode: QuantumMode = app.state.quantum_mode
    await quantum_mode.stop()
    return QuantumStatusResponse(**quantum_mode.status())


@app.get("/quantum/status", response_model=QuantumStatusResponse)
async def quantum_status() -> QuantumStatusResponse:
    quantum_mode: QuantumMode = app.state.quantum_mode
    return QuantumStatusResponse(**quantum_mode.status())


@app.get("/graph/snapshot", response_model=GraphSnapshotResponse)
async def graph_snapshot() -> GraphSnapshotResponse:
    """Stato corrente completo del grafo, usato dal pannello Electron al
    primo caricamento e ogni volta che riceve un evento 'graph-updated'."""
    nodes, edges = get_graph_snapshot(app.state.conn)
    return GraphSnapshotResponse(nodes=nodes, edges=edges)


@app.get("/conversation/history", response_model=ConversationHistoryResponse)
async def conversation_history(limit: int = 100) -> ConversationHistoryResponse:
    """Cronologia reale della conversazione (testo e voce insieme, sono lo
    stesso flusso in episodic_events), usata dalla finestra chat per mostrare
    lo storico vero invece di partire vuota ad ogni apertura."""
    events = episodic.get_recent_events(app.state.conn, limit=limit)
    ordered = list(reversed(events))  # get_recent_events e' piu' recenti prima, qui serve cronologico
    turns = [
        ConversationTurnOut(id=e["id"], event_type=e["event_type"], content=e["content"], created_at=e["created_at"])
        for e in ordered
        if e["event_type"] in ("user_message", "bot_reply")
    ]
    return ConversationHistoryResponse(turns=turns)


@app.post("/admin/reset")
async def admin_reset() -> dict[str, str]:
    """Cancella tutta la memoria (episodica, semantica, grafo). Azione
    distruttiva innescata solo dalla UI di Electron dopo che l'utente ha
    scritto esplicitamente la parola di conferma (vedi settings-window lato
    Electron): brain non ha un suo secondo livello di conferma, si fida che
    chi chiama questo endpoint l'abbia gia' ottenuta."""
    reset_all_memory(app.state.conn)
    app.state.event_bus.publish("graph-updated", {})
    app.state.logger.warning("Reset completo della memoria eseguito su richiesta dell'utente")
    return {"status": "reset completato"}


@app.post("/shutdown", status_code=202)
async def shutdown() -> dict[str, str]:
    """Spegnimento pulito richiesto dal process-supervisor Electron: imposta
    should_exit sul server uvicorn (vedi __main__.py). Il resto della pulizia
    (chiusura client Ollama, connessione DB) avviene comunque nel blocco dopo
    la yield in lifespan(), che gira regolarmente allo shutdown del server."""
    logger = app.state.logger
    logger.info("Richiesta di shutdown ricevuta")
    server = getattr(app.state, "uvicorn_server", None)
    if server is not None:
        server.should_exit = True
    return {"status": "shutting down"}
