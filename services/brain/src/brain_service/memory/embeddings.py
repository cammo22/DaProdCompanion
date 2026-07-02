"""
Generazione di embedding via il modello configurato (nomic-embed-text di
default) attraverso l'endpoint /api/embed di Ollama, e loro serializzazione
nel formato binario che sqlite-vec si aspetta per le colonne FLOAT[N].
"""

from __future__ import annotations

import struct

import httpx


def serialize_embedding(vector: list[float]) -> bytes:
    """Converte un embedding in float32 raw, il formato richiesto da sqlite-vec."""
    return struct.pack(f"{len(vector)}f", *vector)


async def generate_embedding(client: httpx.AsyncClient, *, model: str, text: str) -> list[float]:
    response = await client.post("/api/embed", json={"model": model, "input": text})
    response.raise_for_status()
    data = response.json()
    return data["embeddings"][0]
