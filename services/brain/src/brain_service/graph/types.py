"""Tipi di nodo/arco del grafo di conoscenza, condivisi tra dreaming e
Quantum mode (entrambi popolano lo stesso grafo con lo stesso vocabolario)."""

from __future__ import annotations

ENTITY_TYPES = ["Persona", "Evento", "Concetto", "Luogo"]
EDGE_TYPES = ["conosce", "riguarda", "e_avvenuto_in", "e_collegato_a"]

EDGE_TYPE_LABELS = {
    "conosce": "conosce",
    "riguarda": "riguarda",
    "e_avvenuto_in": "e' avvenuto in",
    "e_collegato_a": "e' collegato a",
}
