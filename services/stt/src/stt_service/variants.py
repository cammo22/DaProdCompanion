"""
Caricamento delle varianti di trascrizione raccolte dalla calibrazione del
wake-word: un JSON con un array di stringhe sotto SANDBOX_ROOT. Se il file
non esiste ancora (calibrazione mai eseguita), restituisce una lista vuota:
il wake-word matching si affida solo al nome esatto e al fuzzy-match
generico su singola parola.
"""

from __future__ import annotations

import json
from pathlib import Path

from companion_shared.sandbox import FilesystemGuard

VARIANTS_FILENAME = "wake_word_variants.json"


def load_extra_variants(guard: FilesystemGuard, sandbox_root: Path) -> list[str]:
    path = guard.resolve_and_check(sandbox_root / VARIANTS_FILENAME, purpose="lettura varianti wake-word")
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [str(v) for v in data] if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_extra_variants(guard: FilesystemGuard, sandbox_root: Path, variants: list[str]) -> None:
    path = guard.resolve_and_check(sandbox_root / VARIANTS_FILENAME, purpose="scrittura varianti wake-word")
    path.write_text(json.dumps(variants, ensure_ascii=False, indent=2), encoding="utf-8")
