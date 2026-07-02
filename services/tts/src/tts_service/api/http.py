"""
API REST di tts_service: /health, /voices, /speak (genera l'audio e lo scrive
sotto SANDBOX_ROOT/audio_cache tramite il wrapper di sandboxing, come ogni
altro dato del companion), /shutdown per lo spegnimento pulito.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import soundfile as sf
from companion_shared.config import ensure_bot_name, load_settings
from companion_shared.logging import setup_logging
from companion_shared.sandbox import FilesystemGuard
from fastapi import FastAPI, HTTPException

from ..engine.kokoro_engine import KokoroEngine
from ..queueing.audio_queue import AudioQueue
from .schemas import HealthResponse, SpeakRequest, SpeakResponse, VoicesResponse

ITALIAN_VOICES = {"if_sara": "femminile", "im_nicola": "maschile"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = ensure_bot_name(load_settings())
    sandbox_root = settings.resolved_sandbox_root()
    log_dir = settings.resolved_log_dir()

    app_logger = setup_logging(service="tts", log_dir=log_dir, level=settings.log_level)

    guard = FilesystemGuard(sandbox_root, service="tts", log_dir=log_dir)
    audio_cache_dir = guard.resolve_and_check(sandbox_root / "audio_cache", purpose="cartella cache audio")
    audio_cache_dir.mkdir(parents=True, exist_ok=True)

    app_logger.info("Carico la pipeline Kokoro (puo' richiedere qualche secondo al primo avvio)...")
    engine = KokoroEngine(lang_code="i")
    app_logger.info("Pipeline Kokoro pronta.")

    app.state.settings = settings
    app.state.guard = guard
    app.state.engine = engine
    app.state.queue = AudioQueue()
    app.state.logger = app_logger
    app.state.voice_id = settings.tts_voice_id or "if_sara"

    yield


app = FastAPI(title="tts_service", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/voices", response_model=VoicesResponse)
async def voices() -> VoicesResponse:
    return VoicesResponse(voices=ITALIAN_VOICES, current=app.state.voice_id)


@app.post("/speak", response_model=SpeakResponse)
async def speak(request: SpeakRequest) -> SpeakResponse:
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Il testo non puo' essere vuoto")

    engine: KokoroEngine = app.state.engine
    queue: AudioQueue = app.state.queue
    guard: FilesystemGuard = app.state.guard
    logger = app.state.logger

    voice = request.voice or app.state.voice_id
    speed = request.speed if request.speed is not None else app.state.settings.tts_speed

    def _synthesize():
        return engine.synthesize(request.text, voice=voice, speed=speed)

    try:
        audio, duration = await queue.synthesize(_synthesize)
    except Exception as exc:
        logger.error("Sintesi fallita: %s", exc)
        raise HTTPException(status_code=502, detail="Sintesi vocale fallita") from exc

    filename = f"{uuid.uuid4().hex}.wav"
    audio_path = guard.resolve_and_check(
        app.state.settings.resolved_sandbox_root() / "audio_cache" / filename,
        purpose="scrittura audio sintetizzato",
    )
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(audio_path, audio, engine.sample_rate)

    return SpeakResponse(audio_path=str(audio_path), duration_seconds=duration)


@app.post("/shutdown", status_code=202)
async def shutdown() -> dict[str, str]:
    app.state.logger.info("Richiesta di shutdown ricevuta")
    server = getattr(app.state, "uvicorn_server", None)
    if server is not None:
        server.should_exit = True
    return {"status": "shutting down"}
