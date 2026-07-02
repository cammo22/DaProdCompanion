"""Modelli Pydantic per le risposte REST di stt_service."""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class DeviceOut(BaseModel):
    index: int
    name: str


class DevicesResponse(BaseModel):
    devices: list[DeviceOut]
    current: int | None


class MuteStateResponse(BaseModel):
    muted: bool


class SpeakingMuteRequest(BaseModel):
    muted: bool
