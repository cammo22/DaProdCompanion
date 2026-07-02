"""
Entry point di stt_service: risolve il first-run setup (se necessario) prima
di avviare il server ASGI, poi usa uvicorn.Server in modo programmatico (come
brain_service e tts_service) per supportare /shutdown in modo cross-platform.
"""

from __future__ import annotations

import asyncio

import uvicorn

from companion_shared.config import ensure_bot_name, load_settings


def main() -> None:
    settings = ensure_bot_name(load_settings())

    from stt_service.api.http import app  # import ritardato: dopo ensure_bot_name

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=settings.stt_http_port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)
    app.state.uvicorn_server = server

    asyncio.run(server.serve())


if __name__ == "__main__":
    main()
