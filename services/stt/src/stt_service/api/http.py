"""
API REST di stt_service: /health per il readiness check del supervisor
Electron, /shutdown per lo spegnimento pulito. L'ascolto vero e proprio non
e' un endpoint: parte da solo nel lifespan, gira in un thread dedicato (la
cattura microfono e' bloccante) che pubblica i segmenti riconosciuti
sull'event loop asyncio principale tramite run_coroutine_threadsafe.
"""

from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager

from companion_shared.config import ensure_bot_name, load_settings
from companion_shared.logging import setup_logging
from companion_shared.sandbox import FilesystemGuard
from fastapi import FastAPI

from ..audio.capture import listen_loop
from ..audio.devices import list_input_devices
from ..brain_client import BrainClient
from ..engine.whisper_engine import WhisperEngine
from ..pipeline import VoicePipeline
from ..variants import load_extra_variants
from .schemas import DevicesResponse, HealthResponse, MuteStateResponse, SpeakingMuteRequest


class MicMuteState:
    """Contenitore mutabile condiviso tra il thread di cattura (legge tramite
    is_muted, passato a listen_loop) e gli endpoint /mic/* (scrivono): un
    bool locale nel lifespan non sarebbe raggiungibile dagli handler HTTP,
    definiti come funzioni a modulo separate che vedono solo app.state.

    Due cause di mute separate e indipendenti, non un unico bool: se fossero
    lo stesso flag, un mute automatico durante la riproduzione TTS potrebbe
    riattivare per sbaglio il microfono che l'utente aveva mutato lui stesso
    a mano (o viceversa, restare mutato dopo la riproduzione se l'utente
    aveva smutato nel frattempo). 'muted' e' vero se una delle due lo e'."""

    def __init__(self) -> None:
        self.manual_muted = False
        self.speaking_muted = False

    @property
    def muted(self) -> bool:
        return self.manual_muted or self.speaking_muted


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = ensure_bot_name(load_settings())
    sandbox_root = settings.resolved_sandbox_root()
    log_dir = settings.resolved_log_dir()

    app_logger = setup_logging(service="stt", log_dir=log_dir, level=settings.log_level)
    guard = FilesystemGuard(sandbox_root, service="stt", log_dir=log_dir)

    app_logger.info("Carico il modello Whisper (puo' richiedere qualche secondo al primo avvio)...")
    engine = WhisperEngine("small")
    app_logger.info("Modello Whisper pronto.")

    brain = BrainClient(f"http://127.0.0.1:{settings.brain_http_port}")
    extra_variants = load_extra_variants(guard, sandbox_root)

    pipeline = VoicePipeline(
        engine=engine,
        brain=brain,
        bot_name=settings.bot_name,
        extra_variants=extra_variants,
    )

    main_loop = asyncio.get_event_loop()
    stop_event = threading.Event()
    mute_state = MicMuteState()

    def _notify(event_type: str) -> None:
        async def _do() -> None:
            try:
                await brain.notify_event(event_type)
            except Exception:
                app_logger.exception("Notifica evento '%s' a brain_service fallita", event_type)

        asyncio.run_coroutine_threadsafe(_do(), main_loop)

    def on_segment(audio):
        asyncio.run_coroutine_threadsafe(pipeline.handle_segment(audio), main_loop)

    listener_thread = threading.Thread(
        target=listen_loop,
        kwargs={
            "on_segment": on_segment,
            "device_index": settings.mic_device_index,
            "stop_flag": stop_event.is_set,
            "on_listening_start": lambda: _notify("listening-started"),
            "on_listening_end": lambda: _notify("listening-finished"),
            "is_muted": lambda: mute_state.muted,
        },
        daemon=True,
    )
    listener_thread.start()

    app.state.settings = settings
    app.state.guard = guard
    app.state.logger = app_logger
    app.state.brain = brain
    app.state.stop_event = stop_event
    app.state.mute_state = mute_state

    app_logger.info("stt_service pronto: ascolto attivo per il nome '%s'", settings.bot_name)

    yield

    stop_event.set()
    await brain.aclose()


app = FastAPI(title="stt_service", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/devices", response_model=DevicesResponse)
async def devices() -> DevicesResponse:
    return DevicesResponse(devices=list_input_devices(), current=app.state.settings.mic_device_index)


@app.post("/mic/toggle-mute", response_model=MuteStateResponse)
async def toggle_mute() -> MuteStateResponse:
    """Toggle manuale, azionato dal pulsante sull'avatar: agisce solo sul
    flag 'manuale', mai su quello 'in riproduzione' (vedi MicMuteState)."""
    state: MicMuteState = app.state.mute_state
    state.manual_muted = not state.manual_muted
    app.state.logger.info("Microfono %s (manuale)", "mutato" if state.manual_muted else "riattivato")
    return MuteStateResponse(muted=state.muted)


@app.get("/mic/mute-state", response_model=MuteStateResponse)
async def mute_state_endpoint() -> MuteStateResponse:
    return MuteStateResponse(muted=app.state.mute_state.muted)


@app.post("/mic/speaking-mute", response_model=MuteStateResponse)
async def speaking_mute(request: SpeakingMuteRequest) -> MuteStateResponse:
    """Chiamato da Electron esattamente quando inizia/finisce la riproduzione
    audio (evento 'play'/'ended' reale, non una stima della durata): evita
    che il microfono sempre acceso capti la voce del companion dalle casse e
    la scambi per un nuovo comando (rischio di auto-innesco se una risposta
    contiene il nome del bot)."""
    state: MicMuteState = app.state.mute_state
    state.speaking_muted = request.muted
    return MuteStateResponse(muted=state.muted)


@app.post("/shutdown", status_code=202)
async def shutdown() -> dict[str, str]:
    logger = app.state.logger
    logger.info("Richiesta di shutdown ricevuta")
    server = getattr(app.state, "uvicorn_server", None)
    if server is not None:
        server.should_exit = True
    return {"status": "shutting down"}
