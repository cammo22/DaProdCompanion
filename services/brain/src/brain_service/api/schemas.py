"""Modelli Pydantic per le richieste/risposte REST di brain_service."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    # "voice" arriva da stt_service: brain non tratta la conversazione in modo
    # diverso, ma pubblica eventi extra sul bus (vedi http.py) perche' a
    # differenza della chat testuale, il chiamante vocale non e' in ascolto di
    # una risposta HTTP a cui reagire nell'interfaccia — serve un canale push.
    source: Literal["text", "voice"] = "text"


class ChatResponse(BaseModel):
    reply: str
    audio_path: str | None = None
    duration_seconds: float | None = None
    used_memory: bool = False


class VoiceEventRequest(BaseModel):
    type: Literal[
        "listening-started",
        "listening-finished",
        "recording-started",
        "recording-finished",
        "wake-word-detected",
    ]


class HealthResponse(BaseModel):
    status: str
    bot_name: str


class DreamingRunResponse(BaseModel):
    consolidated_events: int


class GraphNodeOut(BaseModel):
    id: int
    node_type: str
    label: str


class GraphEdgeOut(BaseModel):
    id: int
    source_node_id: int
    target_node_id: int
    edge_type: str


class GraphSnapshotResponse(BaseModel):
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]


class ConversationTurnOut(BaseModel):
    id: int
    event_type: Literal["user_message", "bot_reply"]
    content: str
    created_at: str


class ConversationHistoryResponse(BaseModel):
    turns: list[ConversationTurnOut]


class DreamingStatusResponse(BaseModel):
    last_dream_at: str | None
    next_scheduled_at: str | None
