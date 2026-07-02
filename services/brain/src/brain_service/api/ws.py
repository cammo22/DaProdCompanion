"""
Endpoint WebSocket per gli eventi push da brain verso Electron: dreaming
avviato/finito (per la bubble "sognando..." sull'avatar), aggiornamenti del
grafo (per il pannello cervellone). Un solo canale, eventi tipati con 'type'
come discriminante (vedi events/bus.py).
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..events.bus import EventBus

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    bus: EventBus = websocket.app.state.event_bus
    queue = bus.subscribe()
    try:
        while True:
            message = await queue.get()
            await websocket.send_text(message)
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(queue)
