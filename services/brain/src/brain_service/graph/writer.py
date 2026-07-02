"""
Scrittura di nodi e archi nel grafo di conoscenza ("cervellone"), con
deduplica: rilanciando il dreaming piu' volte non si vogliono nodi duplicati
per la stessa persona/concetto/luogo, ne' archi duplicati tra la stessa coppia
di nodi con lo stesso tipo di relazione.
"""

from __future__ import annotations

import sqlite3

from companion_shared.db import write_lock


def find_or_create_node(conn: sqlite3.Connection, *, node_type: str, label: str) -> int:
    with write_lock:
        row = conn.execute(
            "SELECT id FROM graph_nodes WHERE node_type = ? AND lower(label) = lower(?)",
            (node_type, label),
        ).fetchone()
        if row is not None:
            return row["id"]

        cursor = conn.execute(
            "INSERT INTO graph_nodes (node_type, label) VALUES (?, ?)",
            (node_type, label),
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
