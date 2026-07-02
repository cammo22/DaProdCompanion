"""
Esportazione in markdown della memoria, in aggiunta a SQLite (non al posto):
un file per entita' del grafo (persone/eventi/concetti/luoghi con le loro
connessioni, stesso contenuto del pannello "cervellone" quando clicchi un
nodo) piu' un file datato per ogni ciclo di dreaming col riassunto prodotto.
Pensata per essere sfogliata a mano (stile vault di note tipo Obsidian), non
per essere riletta dal companion: la fonte di verita' per il retrieval resta
SQLite + sqlite-vec. Passa sempre da FilesystemGuard, come ogni altro accesso
al filesystem in questo progetto.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

from companion_shared.sandbox import FilesystemGuard

from ..graph.snapshot import get_graph_snapshot

_EDGE_TYPE_LABELS = {
    "conosce": "conosce",
    "riguarda": "riguarda",
    "e_avvenuto_in": "e' avvenuto in",
    "e_collegato_a": "e' collegato a",
}


def _slugify(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return slug or "senza-nome"


def _entity_markdown(node: dict, outgoing: list[dict], incoming: list[dict], node_by_id: dict[int, dict]) -> str:
    lines = [f"# {node['label']}", "", f"**Tipo**: {node['node_type']}", "", "## Connessioni"]
    if not outgoing and not incoming:
        lines.append("")
        lines.append("Nessuna connessione ancora.")
    for edge in outgoing:
        target = node_by_id.get(edge["target_node_id"])
        target_label = target["label"] if target else f"#{edge['target_node_id']}"
        edge_label = _EDGE_TYPE_LABELS.get(edge["edge_type"], edge["edge_type"])
        lines.append(f"- {edge_label} → [[{target_label}]]")
    for edge in incoming:
        source = node_by_id.get(edge["source_node_id"])
        source_label = source["label"] if source else f"#{edge['source_node_id']}"
        edge_label = _EDGE_TYPE_LABELS.get(edge["edge_type"], edge["edge_type"])
        lines.append(f"- [[{source_label}]] → {edge_label}")
    return "\n".join(lines) + "\n"


def write_entity_files(conn: sqlite3.Connection, *, guard: FilesystemGuard, sandbox_root: Path) -> None:
    """Riscrive tutti i file entita' dallo stato corrente del grafo: il grafo
    di un companion personale resta piccolo, rigenerare tutto ad ogni ciclo
    e' piu' semplice e piu' robusto che tracciare cosa e' cambiato."""
    nodes, edges = get_graph_snapshot(conn)
    node_by_id = {n["id"]: n for n in nodes}

    for node in nodes:
        outgoing = [e for e in edges if e["source_node_id"] == node["id"]]
        incoming = [e for e in edges if e["target_node_id"] == node["id"]]
        content = _entity_markdown(node, outgoing, incoming, node_by_id)
        file_path = sandbox_root / "memoria" / "entita" / f"{_slugify(node['label'])}.md"
        with guard.open_sandboxed(file_path, "w", purpose="scrittura export markdown entita'", encoding="utf-8") as f:
            f.write(content)


def write_dream_summary(summary: str, *, guard: FilesystemGuard, sandbox_root: Path) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_path = sandbox_root / "memoria" / "sogni" / f"{timestamp}.md"
    content = f"# Sogno del {timestamp}\n\n{summary}\n"
    with guard.open_sandboxed(file_path, "w", purpose="scrittura riassunto sogno", encoding="utf-8") as f:
        f.write(content)
