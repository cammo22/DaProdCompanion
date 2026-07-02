"""
Configurazione centrale del companion, condivisa da tutti i servizi Python.

Legge un unico file .env dalla radice del repo (fonte di verita' unica, letta anche
da Electron lato Node in Fase 2). Se BOT_NAME non e' ancora impostato, i valori
derivati da esso (SANDBOX_ROOT, DB, log) restano irrisolvibili finche' non si
completa il first-run setup (vedi first_run.py).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _repo_root() -> Path:
    # Questo file vive in <repo>/shared/src/companion_shared/config/settings.py:
    # 5 livelli sopra c'e' la radice del repo. Il layout del monorepo e' fisso,
    # quindi la risalita per parent e' affidabile.
    return Path(__file__).resolve().parents[4]


REPO_ROOT = _repo_root()
ENV_FILE = REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    bot_name: str = ""
    sandbox_root: Path | None = None

    ollama_host: str = "http://127.0.0.1:11434"
    brain_model_tag: str = "gemma4:e4b-it-qat"
    brain_model_num_ctx: int = 32768
    vision_model_tag: str = "gemma4:e4b-it-qat"
    embedding_model_tag: str = "nomic-embed-text"

    dreaming_interval_cron: str = "0 4 * * *"
    proactive_tick_interval_seconds: int = 300

    webcam_device_index: int = 0
    face_model_name: str = "buffalo_s"
    force_cpu_insightface: bool = True

    force_cpu_kokoro: bool = True
    tts_voice_id: str = ""
    tts_speed: float = 1.15

    brain_http_port: int = 8770
    webcam_http_port: int = 8771
    tts_http_port: int = 8772
    stt_http_port: int = 8773

    mic_device_index: int | None = None

    log_level: str = "INFO"

    @field_validator("sandbox_root", "mic_device_index", mode="before")
    @classmethod
    def _blank_env_value_as_none(cls, v: object) -> object:
        # SANDBOX_ROOT= o MIC_DEVICE_INDEX= (vuoti) nel .env arrivano qui come
        # stringa vuota, non None: vanno normalizzati esplicitamente, altrimenti
        # verrebbero risolti come Path("") o fallirebbero il parsing a int.
        if v == "":
            return None
        return v

    def has_bot_name(self) -> bool:
        return bool(self.bot_name.strip())

    def resolved_sandbox_root(self) -> Path:
        if self.sandbox_root is not None:
            return self.sandbox_root
        if not self.has_bot_name():
            raise RuntimeError(
                "BOT_NAME non e' impostato: esegui companion_shared.config.first_run.ensure_bot_name() "
                "prima di risolvere la sandbox."
            )
        return Path.home() / "Desktop" / self.bot_name

    def resolved_db_path(self) -> Path:
        return self.resolved_sandbox_root() / "db" / "companion.db"

    def resolved_log_dir(self) -> Path:
        return self.resolved_sandbox_root() / "logs"


def load_settings() -> Settings:
    """Carica (o ricarica) le impostazioni da .env. Va richiamata dopo che
    first_run.ensure_bot_name() ha eventualmente scritto BOT_NAME, per rileggere
    il valore aggiornato."""
    return Settings()
