"""
Entry point di tts_service: propaga FORCE_CPU_KOKORO nell'ambiente PRIMA di
importare l'app (che importa kokoro_engine, il quale deve vedere questa
variabile prima di importare torch/kokoro), poi avvia uvicorn in modo
programmatico per supportare /shutdown come brain_service.
"""

from __future__ import annotations

import asyncio
import os

import uvicorn

from companion_shared.config import ensure_bot_name, load_settings


def main() -> None:
    settings = ensure_bot_name(load_settings())
    os.environ["FORCE_CPU_KOKORO"] = str(settings.force_cpu_kokoro).lower()

    from tts_service.api.http import app  # import ritardato: dopo aver settato FORCE_CPU_KOKORO

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=settings.tts_http_port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)
    app.state.uvicorn_server = server

    asyncio.run(server.serve())


if __name__ == "__main__":
    main()
