-- Traccia quando un nodo del grafo e' stato aggiornato l'ultima volta (non solo
-- creato): serve per l'export markdown con frontmatter in stile Obsidian
-- (title/created/updated/type/tags/sources/confidence), dove 'updated' deve
-- riflettere l'ultima volta che il dreaming ha ritoccato quel nodo, non solo
-- la sua creazione iniziale.
ALTER TABLE graph_nodes ADD COLUMN updated_at TEXT;
UPDATE graph_nodes SET updated_at = created_at WHERE updated_at IS NULL;
