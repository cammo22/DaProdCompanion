"""Modelli Pydantic per le richieste/risposte REST di tts_service."""

from __future__ import annotations

from pydantic import BaseModel


class SpeakRequest(BaseModel):
    text: str
    voice: str | None = None
    speed: float | None = None


class SpeakResponse(BaseModel):
    audio_path: str
    duration_seconds: float


class VoicesResponse(BaseModel):
    voices: dict[str, str]
    current: str


class HealthResponse(BaseModel):
    status: str
