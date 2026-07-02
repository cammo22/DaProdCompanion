-- Schema iniziale del companion. Copre tutte le 6 fasi fin da subito (le tabelle
-- delle fasi future restano semplicemente vuote finche' non vengono usate), cosi'
-- non serve una nuova migrazione a ogni fase.

-- Memoria episodica grezza (Fase 1): ogni interazione o evento osservato.
CREATE TABLE IF NOT EXISTS episodic_events (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    event_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT,
    consolidated INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_episodic_events_created_at ON episodic_events (created_at);
CREATE INDEX IF NOT EXISTS idx_episodic_events_consolidated ON episodic_events (consolidated);

-- Memoria semantica consolidata dal dreaming (Fase 5).
CREATE TABLE IF NOT EXISTS semantic_memories (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    summary TEXT NOT NULL,
    source_event_ids TEXT
);

-- Tabella virtuale sqlite-vec con gli embedding della memoria semantica (Fase 5).
-- Dimensione 768 per nomic-embed-text: da confermare al primo utilizzo reale del modello.
CREATE VIRTUAL TABLE IF NOT EXISTS semantic_memories_vec USING vec0(
    memory_id INTEGER PRIMARY KEY,
    embedding FLOAT[768]
);

-- Knowledge graph (Fase 6).
CREATE TABLE IF NOT EXISTS graph_nodes (
    id INTEGER PRIMARY KEY,
    node_type TEXT NOT NULL,
    label TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS graph_edges (
    id INTEGER PRIMARY KEY,
    source_node_id INTEGER NOT NULL REFERENCES graph_nodes (id),
    target_node_id INTEGER NOT NULL REFERENCES graph_nodes (id),
    edge_type TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON graph_edges (source_node_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON graph_edges (target_node_id);

-- Riconoscimento facciale (Fase 4).
CREATE TABLE IF NOT EXISTS known_people (
    id INTEGER PRIMARY KEY,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    graph_node_id INTEGER REFERENCES graph_nodes (id)
);

CREATE TABLE IF NOT EXISTS face_embeddings (
    id INTEGER PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES known_people (id),
    embedding BLOB NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Audit trail del wrapper di sandboxing filesystem (Fase 1).
CREATE TABLE IF NOT EXISTS sandbox_access_log (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    service TEXT NOT NULL,
    requested_path TEXT NOT NULL,
    allowed INTEGER NOT NULL,
    reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_sandbox_access_log_timestamp ON sandbox_access_log (timestamp);
