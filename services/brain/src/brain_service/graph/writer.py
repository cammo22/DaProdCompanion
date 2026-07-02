"""
Scrittura di nodi e archi nel grafo di conoscenza ("cervellone"), con
deduplica: rilanciando il dreaming piu' volte non si vogliono nodi duplicati
per la stessa persona/concetto/luogo, ne' archi duplicati tra la stessa coppia
di nodi con lo stesso tipo di relazione.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from companion_shared.db import write_lock


def _merge_metadata(existing_raw: str | None, *, tags: list[str], confidence: float | None, source: str | None) -> str:
    """Unisce i metadati nuovi a quelli gia' salvati sul nodo, invece di
    sovrascriverli: un nodo puo' essere ritoccato da molti cicli di dreaming
    diversi nel tempo, e ogni ciclo aggiunge la propria fonte senza cancellare
    quelle precedenti (altrimenti il campo 'sources' del frontmatter
    mostrerebbe solo l'ultimo dreaming che l'ha citato)."""
    existing = json.loads(existing_raw) if existing_raw else {}
    merged_tags = sorted(set(existing.get("tags", [])) | set(tags))
    merged_sources = list(existing.get("sources", []))
    if source and source not in merged_sources:
        merged_sources.append(source)
    merged_confidence = confidence if confidence is not None else existing.get("confidence")
    return json.dumps({"tags": merged_tags, "sources": merged_sources, "confidence": merged_confidence})


def find_or_create_node(
    conn: sqlite3.Connection,
    *,
    node_type: str,
    label: str,
    tags: list[str] | None = None,
    confidence: float | None = None,
    source: str | None = None,
) -> int:
    now = datetime.now().isoformat()
    with write_lock:
        row = conn.execute(
            "SELECT id, metadata FROM graph_nodes WHERE node_type = ? AND lower(label) = lower(?)",
            (node_type, label),
        ).fetchone()
        metadata = _merge_metadata(row["metadata"] if row else None, tags=tags or [], confidence=confidence, source=source)

        if row is not None:
            conn.execute(
                "UPDATE graph_nodes SET metadata = ?, updated_at = ? WHERE id = ?",
                (metadata, now, row["id"]),
            )
            conn.commit()
            return row["id"]

        cursor = conn.execute(
            "INSERT INTO graph_nodes (node_type, label, metadata, updated_at) VALUES (?, ?, ?, ?)",
            (node_type, label, metadata, now),
        )
        conn.commit()
        return cursor.lastrowid


def find_or_create_edge(conn: sqlite3.Connection, *, source_node_id: int, target_node_id: int, edge_type: str) -> int:
    with write_lock:
        row = conn.execute(
            "SELECT id FROM graph_edges WHERE source_node_id = ? AND target_node_id = ? AND edge_type = ?",
            (source_node_id, target_node_id, edge_type),
        ).fetchone()
        if row is not None:
            return row["id"]

        cursor = conn.execute(
            "INSERT INTO graph_edges (source_node_id, target_node_id, edge_type) VALUES (?, ?, ?)",
            (source_node_id, target_node_id, edge_type),
        )
        conn.commit()
        return cursor.lastrowid
