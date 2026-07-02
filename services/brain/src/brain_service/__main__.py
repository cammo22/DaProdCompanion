"""
Entry point di brain_service: risolve il first-run setup (se necessario) PRIMA
di avviare il server ASGI, cosi' il prompt interattivo da terminale non deve
convivere con l'event loop asyncio di uvicorn.

Usa uvicorn.Server in modo programmatico (invece di uvicorn.run) cosi' l'endpoint
POST /shutdown puo' fermare il server impostando should_exit=True: e' il modo
cross-platform per farlo, dato che l'affidarsi ai segnali POSIX (SIGTERM) non
funziona in modo uniforme su Windows, dove questo servizio viene normalmente
avviato come processo figlio dal supervisore Electron (Fase 2).
"""

from __future__ import annotations

import asyncio

import uvicorn

from companion_shared.config import ensure_bot_name, load_settings


def main() -> None:
    settings = ensure_bot_name(load_settings())

    from brain_service.api.http import app  # import ritardato: dopo ensure_bot_name

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=settings.brain_http_port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)
    app.state.uvicorn_server = server  # letto dall'endpoint /shutdown

    asyncio.run(server.serve())


if __name__ == "__main__":
    main()
