"""
Whitelist esplicita di percorsi fuori dalla sandbox, autorizzati dall'utente.

Persistita come JSON leggibile/modificabile a mano in <SANDBOX_ROOT>/whitelist.json.
Non e' mai popolata implicitamente: ogni voce richiede un'autorizzazione esplicita
(vedi add_entry), mai un accesso libero di default al resto del disco.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

_lock = threading.Lock()


@dataclass
class WhitelistEntry:
    path: str
    reason: str
    added_at: str


def _whitelist_file(sandbox_root: Path) -> Path:
    return sandbox_root / "whitelist.json"


def load_entries(sandbox_root: Path) -> list[WhitelistEntry]:
    path = _whitelist_file(sandbox_root)
    if not path.exists():
        return []
    with _lock, path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return [WhitelistEntry(**item) for item in raw]


def is_whitelisted(sandbox_root: Path, target: Path) -> bool:
    """True se 'target' e' un percorso whitelistato o e' contenuto in una cartella whitelistata."""
    target = target.resolve()
    for entry in load_entries(sandbox_root):
        allowed = Path(entry.path).resolve()
        if target == allowed or allowed in target.parents:
            return True
    return False


def add_entry(sandbox_root: Path, target: Path, reason: str) -> WhitelistEntry:
    """Autorizza esplicitamente un percorso fuori sandbox. Va invocata solo in risposta
    a un'azione esplicita dell'utente, mai automaticamente dal codice applicativo."""
    entries = load_entries(sandbox_root)
    entry = WhitelistEntry(
        path=str(target.resolve()),
        reason=reason,
        added_at=datetime.now(timezone.utc).isoformat(),
    )
    entries.append(entry)
    path = _whitelist_file(sandbox_root)
    with _lock, path.open("w", encoding="utf-8") as f:
        json.dump([asdict(e) for e in entries], f, ensure_ascii=False, indent=2)
    return entry
