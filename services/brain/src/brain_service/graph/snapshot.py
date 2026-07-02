"""Lettura dello stato corrente del grafo, per il pannello Electron."""

from __future__ import annotations

import sqlite3


def get_graph_snapshot(conn: sqlite3.Connection) -> tuple[list[dict], list[dict]]:
    nodes = [
        {
            "id": row["id"],
            "node_type": row["node_type"],
            "label": row["label"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "metadata": row["metadata"],
        }
        for row in conn.execute("SELECT id, node_type, label, created_at, updated_at, metadata FROM graph_nodes")
    ]
    edges = [
        {
            "id": row["id"],
            "source_node_id": row["source_node_id"],
            "target_node_id": row["target_node_id"],
            "edge_type": row["edge_type"],
        }
        for row in conn.execute("SELECT id, source_node_id, target_node_id, edge_type FROM graph_edges")
    ]
    return nodes, edges
