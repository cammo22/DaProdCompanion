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

# Schema PIATTO: una sola relazione tra due nodi per iterazione, campi diretti,
# nessuna indirezione con temp_id, nessun array annidato. Un modello piccolo
# (es. gemma e2b, qwen 4b) riempie 6 campi chiari molto piu' affidabilmente di
# uno schema con liste di oggetti annidati — era il motivo per cui la modalita'
# Quantum "non capiva un cazzo" e falliva il JSON iterazione dopo iterazione.
_ITERATION_SCHEMA = {
    "type": "object",
    "properties": {
        "da": {"type": "string"},
        "tipo_da": {"type": "string", "enum": ENTITY_TYPES},
        "relazione": {"type": "string", "enum": EDGE_TYPES},
        "a": {"type": "string"},
        "tipo_a": {"type": "string", "enum": ENTITY_TYPES},
        "azione": {"type": "string"},
    },
    "required": ["da", "tipo_da", "relazione", "a", "tipo_a", "azione"],
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


# Cap sulle righe di grafo passate nel prompt: per tenere il contesto basso e
# la comprensione alta, non serve dumpare TUTTE le relazioni ad ogni giro.
_MAX_GRAPH_LINES = 40
_MAX_LABELS = 60


def _build_iteration_prompt(*, bot_name: str, nodes: list[dict], edges: list[dict], handoff_note: str) -> str:
    node_by_id = {n["id"]: n for n in nodes}
    labels = [n["label"] for n in nodes][:_MAX_LABELS]

    graph_lines = []
    for edge in edges[-_MAX_GRAPH_LINES:]:
        source = node_by_id.get(edge["source_node_id"])
        target = node_by_id.get(edge["target_node_id"])
        if source and target:
            graph_lines.append(f"{source['label']} {edge['edge_type']} {target['label']}")

    isolated = [
        n["label"]
        for n in nodes
        if not any(e["source_node_id"] == n["id"] or e["target_node_id"] == n["id"] for e in edges)
    ][:20]

    # Istruzione corta, diretta, con esempio concreto. Niente giri di parole:
    # il modello deve capire in due righe cosa fare.
    parts = [
        f"Sei {bot_name}. Stai riordinando quello che sai. Aggiungi UN SOLO collegamento nuovo tra "
        "due cose che gia' conosci (o collega una cosa isolata a una gia' collegata).",
        "",
        "Cose che conosci: " + (", ".join(labels) if labels else "(niente ancora)"),
    ]
    if graph_lines:
        parts.append("\nCollegamenti gia' fatti:\n" + "\n".join(graph_lines))
    if isolated:
        parts.append("\nCose isolate da collegare: " + ", ".join(isolated))
    if handoff_note:
        parts.append("\nAppunto lasciato la volta scorsa: " + handoff_note)
    parts.append(
        "\nRispondi con: da, tipo_da, relazione, a, tipo_a, azione (una frase su cosa hai collegato)."
        "\n- relazione: conosce, riguarda, e_avvenuto_in, e_collegato_a"
        "\n- tipo_da / tipo_a: Persona, Evento, Concetto, Luogo"
        "\nUsa nomi ESATTI dalla lista qui sopra quando colleghi cose che gia' esistono. "
        "Se davvero non trovi nulla di sensato, metti 'da' e 'a' uguali."
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
        bot_name: str = "",
        on_event: Callable[[str, dict], None] | None = None,
    ) -> None:
        self._conn = conn
        self._ollama_host = ollama_host
        self._brain_model_tag = brain_model_tag
        self._num_ctx = num_ctx
        self._bot_name = bot_name
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
        prompt = _build_iteration_prompt(
            bot_name=self._bot_name, nodes=nodes, edges=edges, handoff_note=handoff_note
        )

        response = await client.post(
            "/api/chat",
            json={
                "model": self._brain_model_tag,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "format": _ITERATION_SCHEMA,
                "think": False,
                # Lo schema piatto produce output minuscolo: num_predict basso
                # basta e avanza, non serve piu' il tetto alto anti-troncamento.
                "options": {"num_ctx": self._num_ctx, "num_predict": 512},
            },
        )
        response.raise_for_status()
        try:
            parsed = json.loads(response.json()["message"]["content"])
        except json.JSONDecodeError:
            logger.warning("Quantum: risposta non era JSON valido, salto questa iterazione")
            return

        self._apply_iteration(parsed)

    def _apply_iteration(self, parsed: dict) -> None:
        """Applica una risposta piatta (da/relazione/a) al grafo: crea i due
        nodi (find_or_create dedup per label) e l'arco. Isolata dal resto per
        essere testata senza rete."""
        da = str(parsed.get("da", "")).strip()
        a = str(parsed.get("a", "")).strip()
        relazione = str(parsed.get("relazione", "")).strip()
        azione = str(parsed.get("azione", "")).strip()

        # 'da' e 'a' uguali (o vuoti) = il modello non ha trovato nulla di
        # sensato da collegare in questo giro: non e' un errore, solo un no-op.
        if da and a and da.lower() != a.lower() and relazione in EDGE_TYPES:
            source = f"Quantum del {datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
            source_id = find_or_create_node(
                self._conn, node_type=str(parsed.get("tipo_da", "Concetto")), label=da, source=source
            )
            target_id = find_or_create_node(
                self._conn, node_type=str(parsed.get("tipo_a", "Concetto")), label=a, source=source
            )
            find_or_create_edge(
                self._conn, source_node_id=source_id, target_node_id=target_id, edge_type=relazione
            )
            if self._on_event:
                self._on_event("graph-updated", {})

        if azione and self._on_event:
            self._on_event("quantum-insight", {"insight": azione, "iteration": self._iterations_done + 1})

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
                    "think": False,
                    "options": {"num_ctx": self._num_ctx, "num_predict": 1024},
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
