"""
First-run setup: se BOT_NAME non e' ancora impostato in .env, lo chiede
interattivamente da terminale e lo scrive li'. Va eseguito prima di avviare
qualunque componente che dipenda da SANDBOX_ROOT (che si deriva dal nome).

In Fase 2 questo prompt da terminale verra' affiancato/sostituito da una vera
schermata di onboarding in Electron, ma il contratto resta lo stesso: leggere/
scrivere BOT_NAME nell'unico .env condiviso.
"""

from __future__ import annotations

from pathlib import Path

from .settings import ENV_FILE, Settings, load_settings

_ILLEGAL_FOLDER_CHARS = set('<>:"/\\|?*')


def _is_valid_folder_name(name: str) -> bool:
    if any(ch in _ILLEGAL_FOLDER_CHARS for ch in name):
        return False
    if name in {".", ".."}:
        return False
    return True


def _write_bot_name(bot_name: str) -> None:
    """Scrive/aggiorna BOT_NAME in .env. Non e' un'operazione sandboxed: .env e'
    configurazione del repo (codice), non un dato del companion (che vive sotto
    SANDBOX_ROOT una volta risolto)."""
    lines: list[str] = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()

    found = False
    new_lines = []
    for line in lines:
        if line.strip().startswith("BOT_NAME="):
            new_lines.append(f"BOT_NAME={bot_name}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"BOT_NAME={bot_name}")

    ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def ensure_bot_name(settings: Settings | None = None) -> Settings:
    """Se BOT_NAME e' gia' impostato restituisce le settings invariate. Altrimenti
    chiede il nome da terminale, lo persiste in .env e ricarica le settings."""
    settings = settings or load_settings()
    if settings.has_bot_name():
        return settings

    print()
    print("=== Primo avvio: come vuoi chiamare il tuo companion? ===")
    print("Il nome determina anche la cartella dedicata creata sul Desktop.")
    while True:
        chosen = input("Nome del companion: ").strip()
        if not chosen:
            print("Il nome non puo' essere vuoto, riprova.")
            continue
        if not _is_valid_folder_name(chosen):
            print('Il nome non puo\' contenere: < > : " / \\ | ? *. Riprova.')
            continue
        break

    _write_bot_name(chosen)
    print(f"Fatto: {chosen} usera' la cartella {Path.home() / 'Desktop' / chosen}")
    print()
    return load_settings()
