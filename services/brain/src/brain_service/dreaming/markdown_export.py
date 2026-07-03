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

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from companion_shared.sandbox import FilesystemGuard

from ..graph.snapshot import get_graph_snapshot
from ..graph.types import EDGE_TYPE_LABELS


def _slugify(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return slug or "senza-nome"


def _yaml_scalar(value: str) -> str:
    """Quoting minimo per uno scalare YAML: niente libreria dedicata solo per
    questo, i valori qui sono sempre stringhe brevi (etichette, tag), non
    testo libero che richiederebbe un escaping piu' sofisticato."""
    escaped = value.replace('"', '\\"')
    return f'"{escaped}"'


def _yaml_frontmatter(fields: dict) -> str:
    lines = ["---"]
    for key, value in fields.items():
        if value is None:
            lines.append(f"{key}: null")
        elif isinstance(value, list):
            items = ", ".join(_yaml_scalar(str(v)) for v in value)
            lines.append(f"{key}: [{items}]")
        elif isinstance(value, (int, float)):
            lines.append(f"{key}: {value}")
        else:
            lines.append(f"{key}: {_yaml_scalar(str(value))}")
    lines.append("---")
    return "\n".join(lines)


def _entity_markdown(node: dict, outgoing: list[dict], incoming: list[dict], node_by_id: dict[int, dict]) -> str:
    metadata = json.loads(node["metadata"]) if node.get("metadata") else {}
    frontmatter = _yaml_frontmatter(
        {
            "title": node["label"],
            "created": node.get("created_at"),
            "updated": node.get("updated_at"),
            "type": node["node_type"],
            "tags": metadata.get("tags", []),
            "sources": metadata.get("sources", []),
            "confidence": metadata.get("confidence"),
        }
    )
    lines = [frontmatter, "", f"# {node['label']}", "", "## Connessioni"]
    if not outgoing and not incoming:
        lines.append("")
        lines.append("Nessuna connessione ancora.")
    for edge in outgoing:
        target = node_by_id.get(edge["target_node_id"])
        target_label = target["label"] if target else f"#{edge['target_node_id']}"
        edge_label = EDGE_TYPE_LABELS.get(edge["edge_type"], edge["edge_type"])
        lines.append(f"- {edge_label} → [[{target_label}]]")
    for edge in incoming:
        source = node_by_id.get(edge["source_node_id"])
        source_label = source["label"] if source else f"#{edge['source_node_id']}"
        edge_label = EDGE_TYPE_LABELS.get(edge["edge_type"], edge["edge_type"])
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


def write_dream_summary(summary: str, *, timestamp: str, guard: FilesystemGuard, sandbox_root: Path) -> None:
    file_path = sandbox_root / "memoria" / "sogni" / f"{timestamp}.md"
    content = f"# Sogno del {timestamp}\n\n{summary}\n"
    with guard.open_sandboxed(file_path, "w", purpose="scrittura riassunto sogno", encoding="utf-8") as f:
        f.write(content)


_IDENTITY_FILE = Path("chi-sono.md")
_MAX_IDENTITY_ENTRIES = 30


def _split_identity_sections(text: str) -> tuple[str, list[str]]:
    """Separa l'intestazione ("# Chi sono io, ...") dalle sezioni datate
    ("## AAAA-MM-GG") che seguono, per poterne tenere solo le ultime N senza
    perdere l'intestazione: il diario altrimenti crescerebbe all'infinito."""
    lines = text.split("\n")
    i = 0
    while i < len(lines) and not lines[i].startswith("## "):
        i += 1
    header = "\n".join(lines[:i]).rstrip("\n")
    rest = "\n".join(lines[i:]).strip("\n")
    if not rest:
        return header, []
    sections = [s.strip("\n") for s in re.split(r"\n(?=## )", rest) if s.strip()]
    return header, sections


def append_identity_reflection(reflection: str, *, bot_name: str, guard: FilesystemGuard, sandbox_root: Path) -> None:
    """Pagina 'chi sono' auto-scritta dal companion stesso: non viene
    rigenerata da zero come i file entita' (qui non c'e' uno stato
    strutturato da cui ricostruirla), ma accumulata nel tempo una riflessione
    alla volta, cosi' diventa via via un diario della propria identita' cosi'
    come emerge dalle conversazioni reali, non un testo statico scritto una
    tantum. Tiene solo le ultime _MAX_IDENTITY_ENTRIES sezioni, altrimenti
    dopo mesi di dreaming il file crescerebbe senza limite."""
    file_path = sandbox_root / _IDENTITY_FILE
    try:
        with guard.open_sandboxed(file_path, "r", purpose="lettura pagina identita'", encoding="utf-8") as f:
            existing = f.read()
    except FileNotFoundError:
        existing = f"# Chi sono io, {bot_name}\n"

    header, entries = _split_identity_sections(existing)
    today = datetime.now().strftime("%Y-%m-%d")
    entries.append(f"## {today}\n\n{reflection}")
    entries = entries[-_MAX_IDENTITY_ENTRIES:]

    content = header + "\n\n" + "\n\n".join(entries) + "\n"
    with guard.open_sandboxed(file_path, "w", purpose="scrittura pagina identita'", encoding="utf-8") as f:
        f.write(content)
