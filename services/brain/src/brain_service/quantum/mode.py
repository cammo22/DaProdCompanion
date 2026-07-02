"""
Modalita' Quantum: il companion espande da solo il proprio grafo di
conoscenza per un numero limitato di iterazioni, collegando entita'
esistenti e aggiungendone di nuove senza input dell'utente. E' esclusiva con
l'ascolto vocale e col dreaming normale (sospende entrambi mentre e' attiva,
li riattiva sempre alla fine, anche in caso di errore): altrimenti
competerebbero per lo stesso modello Ollama e lo stesso microfono. Un tetto
massimo di iterazioni per attivazione evita che giri per sempre consumando
calcolo senza supervisione — e' pensata per essere avviata e fermata
dall'utente dal pannello del grafo, non per restare sempre accesa.

Alla fine (fermata manuale o tetto raggiunto) chiede al modello una breve
nota di handoff per il prossimo ciclo Quantum, cosi' non riparte sempre da
zero: e' l'unico stato che sopravvive tra un'attivazione e l'altra, oltre al
grafo stesso.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import httpx
from companion_shared.sandbox import FilesystemGuard

from ..conversation.ollama_client import OllamaClient
from ..conversation.stt_client import SttClient
from ..dreaming.scheduler import DreamingScheduler
from ..graph.snapshot import get_graph_snapshot
from ..graph.types import EDGE_TYPES, ENTITY_TYPES
from ..graph.writer import find_or_create_edge, find_or_create_node

logger = logging.getLogger("brain")

_MAX_ITERATIONS = 20
_HANDOFF_FILE = Path("memoria") / "quantum_handoff.md"

_ITERATION_SCHEMA = {
    "type": "object",
    "properties": {
        "insight": {"type": "string"},
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "temp_id": {"type": "string"},
                    "type": {"type": "string", "enum": ENTITY_TYPES},
                    "label": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number"},
                },
                "required": ["temp_id", "type", "label", "tags", "confidence"],
            },
        },
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_temp_id": {"type": "string"},
                    "target_temp_id": {"type": "string"},
                    "type": {"type": "string", "enum": EDGE_TYPES},
                },
                "required": ["source_temp_id", "target_temp_id", "type"],
            },
        },
    },
    "required": ["insight", "entities", "relations"],
}

_HANDOFF_SCHEMA = {
    "type": "object",
    "properties": {"note": {"type": "string"}},
    "required": ["note"],
}


def _read_handoff_note(*, guard: FilesystemGuard, sandbox_root: Path) -> str:
    try:
        with guard.open_sandboxed(
            sandbox_root / _HANDOFF_FILE, "r", purpose="lettura nota di handoff Quantum", encoding="utf-8"
        ) as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def _write_handoff_note(note: str, *, guard: FilesystemGuard, sandbox_root: Path) -> None:
    with guard.open_sandboxed(
        sandbox_root / _HANDOFF_FILE, "w", purpose="scrittura nota di handoff Quantum", encoding="utf-8"
    ) as f:
        f.write(note.strip() + "\n")


def _build_iteration_prompt(*, nodes: list[dict], edges: list[dict], handoff_note: str) -> str:
    node_by_id = {n["id"]: n for n in nodes}
    graph_lines = []
    for edge in edges:
        source = node_by_id.get(edge["source_node_id"])
        target = node_by_id.get(edge["target_node_id"])
        if source and target:
            graph_lines.append(f"- {source['label']} --{edge['edge_type']}--> {target['label']}")
    isolated = [n["label"] for n in nodes if not any(
        e["source_node_id"] == n["id"] or e["target_node_id"] == n["id"] for e in edges
    )]

    parts = [
        "Sei in 'modalita' Quantum': un ciclo autonomo in cui esplori e arricchisci il tuo grafo "
        "di conoscenza da solo, senza che l'utente ti stia parlando in questo momento. Il tuo "
        "compito e' trovare UN collegamento nuovo, plausibile e utile tra entita' che gia' "
        "conosci (o aggiungere una singola entita' nuova strettamente collegata a una esistente), "
        "usando solo cio' che sai davvero dal grafo qui sotto: NON INVENTARE persone, eventi o "
        "fatti che non siano deducibili da quello che segue.",
        "",
        "Grafo attuale (relazioni note):",
        "\n".join(graph_lines) if graph_lines else "(nessuna relazione ancora)",
    ]
    if isolated:
        parts.append("\nEntita' isolate, senza nessuna connessione (buoni candidati da collegare):")
        parts.append(", ".join(isolated))
    if handoff_note:
        parts.append(f"\nNota lasciata dall'ultimo ciclo Quantum: {handoff_note}")
    parts.append(
        "\nProduci un JSON con: 'insight' (una frase su cosa hai appena collegato o aggiunto e "
        "perche'), 'entities' (di solito 0 o 1 nuova entita', con 'temp_id' arbitrario tipo 'e1', "
        "'tags' e 'confidence' come nel consolidamento normale — riusa il temp_id anche per "
        "un'entita' GIA' esistente se ti serve referenziarla in una relazione, scegliendo un nome "
        "identico alla label esistente), 'relations' (di solito 1 relazione nuova). Se davvero non "
        "trovi nulla di plausibile da collegare, lascia entrambe le liste vuote e spiegalo in "
        "'insight'."
    )
    return "\n".join(parts)


class QuantumMode:
    def __init__(
        self,
        *,
        conn: sqlite3.Connection,
        ollama_host: str,
        brain_model_tag: str,
        num_ctx: int,
        guard: FilesystemGuard,
        sandbox_root: Path,
        dreaming_scheduler: DreamingScheduler,
        stt: SttClient,
        on_event: Callable[[str, dict], None] | None = None,
    ) -> None:
        self._conn = conn
        self._ollama_host = ollama_host
        self._brain_model_tag = brain_model_tag
        self._num_ctx = num_ctx
        self._guard = guard
        self._sandbox_root = sandbox_root
        self._dreaming_scheduler = dreaming_scheduler
        self._stt = stt
        self._on_event = on_event
        self._active = False
        self._iterations_done = 0
        self._task: asyncio.Task | None = None

    def is_active(self) -> bool:
        return self._active

    def status(self) -> dict:
        return {"active": self._active, "iterations_done": self._iterations_done}

    async def start(self) -> None:
        if self._active:
            return
        self._active = True
        self._iterations_done = 0
        self._dreaming_scheduler.suppress()
        await self._set_mic_muted(True)
        if self._on_event:
            self._on_event("quantum-started", {})
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        if not self._active:
            return
        task = self._task
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _set_mic_muted(self, muted: bool) -> None:
        try:
            await self._stt.set_quantum_mute(muted)
        except Exception:
            logger.warning("Quantum: impossibile %s il microfono (stt_service non raggiungibile)", "mutare" if muted else "smutare")

    async def _run_loop(self) -> None:
        try:
            async with httpx.AsyncClient(base_url=self._ollama_host, timeout=180.0) as client:
                for _ in range(_MAX_ITERATIONS):
                    await self._iterate(client)
                    self._iterations_done += 1
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Quantum: ciclo interrotto da un errore")
        finally:
            await self._finish()

    async def _iterate(self, client: httpx.AsyncClient) -> None:
        nodes, edges = get_graph_snapshot(self._conn)
        handoff_note = _read_handoff_note(guard=self._guard, sandbox_root=self._sandbox_root)
        prompt = _build_iteration_prompt(nodes=nodes, edges=edges, handoff_note=handoff_note)

        response = await client.post(
            "/api/chat",
            json={
                "model": self._brain_model_tag,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "format": _ITERATION_SCHEMA,
                "options": {"num_ctx": self._num_ctx, "num_predict": 512},
            },
        )
        response.raise_for_status()
        try:
            parsed = json.loads(response.json()["message"]["content"])
        except json.JSONDecodeError:
            logger.warning("Quantum: risposta non era JSON valido, salto questa iterazione")
            return

        source = f"Quantum del {datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        temp_id_to_node_id: dict[str, int] = {}
        for entity in parsed.get("entities", []):
            node_id = find_or_create_node(
                self._conn,
                node_type=entity["type"],
                label=entity["label"],
                tags=entity.get("tags", []),
                confidence=entity.get("confidence"),
                source=source,
            )
            temp_id_to_node_id[entity["temp_id"]] = node_id

        graph_changed = bool(parsed.get("entities"))
        for relation in parsed.get("relations", []):
            source_id = temp_id_to_node_id.get(relation["source_temp_id"])
            target_id = temp_id_to_node_id.get(relation["target_temp_id"])
            if source_id is None or target_id is None:
                continue
            find_or_create_edge(self._conn, source_node_id=source_id, target_node_id=target_id, edge_type=relation["type"])
            graph_changed = True

        if graph_changed and self._on_event:
            self._on_event("graph-updated", {})

        insight = parsed.get("insight", "").strip()
        if insight and self._on_event:
            self._on_event("quantum-insight", {"insight": insight, "iteration": self._iterations_done + 1})

    async def _write_final_handoff(self, client: httpx.AsyncClient) -> None:
        try:
            response = await client.post(
                "/api/chat",
                json={
                    "model": self._brain_model_tag,
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                "Stai per uscire dalla modalita' Quantum. Lascia una breve nota (2-3 frasi) "
                                "per il tuo prossimo ciclo Quantum: cosa hai esplorato, cosa vale la pena "
                                "approfondire dopo. Rispondi in JSON con il campo 'note'."
                            ),
                        }
                    ],
                    "stream": False,
                    "format": _HANDOFF_SCHEMA,
                    "options": {"num_ctx": self._num_ctx, "num_predict": 256},
                },
            )
            response.raise_for_status()
            note = json.loads(response.json()["message"]["content"]).get("note", "").strip()
            if note:
                _write_handoff_note(note, guard=self._guard, sandbox_root=self._sandbox_root)
        except Exception:
            logger.warning("Quantum: scrittura della nota di handoff fallita, il prossimo ciclo ripartira' senza")

    async def _finish(self) -> None:
        try:
            async with httpx.AsyncClient(base_url=self._ollama_host, timeout=60.0) as client:
                await self._write_final_handoff(client)
        finally:
            self._active = False
            self._task = None
            self._dreaming_scheduler.unsuppress()
            await self._set_mic_muted(False)
            if self._on_event:
                self._on_event("quantum-finished", {"iterations_done": self._iterations_done})
