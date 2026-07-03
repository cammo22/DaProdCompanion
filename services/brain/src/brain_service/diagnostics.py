"""
Controllo dei prerequisiti a monte: brain_service risponde /health con 200
anche se Ollama non e' in esecuzione o il modello configurato non e' stato
scaricato — in quel caso e' solo la PRIMA chat a fallire, con un errore grezzo
che non dice all'utente cosa fare. Questo modulo raccoglie una diagnosi
chiara ("Ollama non raggiungibile", "il modello X non e' scaricato, esegui
ollama pull X") che Electron mostra all'avvio, cosi' il setup iniziale su
Windows e' guidato invece che un fallimento silenzioso.

La logica di confronto tra tag configurato e modelli installati e' isolata in
_model_is_installed() (pura, senza rete) apposta per essere testata con dati
sintetici, senza un'istanza Ollama reale.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger("brain")


@dataclass
class DiagnosticsResult:
    ollama_reachable: bool
    brain_model_present: bool
    embedding_model_present: bool
    brain_model_tag: str
    embedding_model_tag: str
    installed_models: list[str]

    @property
    def all_ok(self) -> bool:
        return self.ollama_reachable and self.brain_model_present and self.embedding_model_present

    def problems(self) -> list[str]:
        """Messaggi pronti da mostrare all'utente, in italiano, ognuno con
        l'azione concreta da fare. Lista vuota se e' tutto a posto."""
        if not self.ollama_reachable:
            return [
                "Ollama non e' in esecuzione o non e' raggiungibile. Avvia Ollama "
                "(https://ollama.com) e riavvia il companion."
            ]
        issues: list[str] = []
        if not self.brain_model_present:
            issues.append(
                f"Il modello per la conversazione '{self.brain_model_tag}' non e' scaricato. "
                f"Esegui: ollama pull {self.brain_model_tag}"
            )
        if not self.embedding_model_present:
            issues.append(
                f"Il modello per gli embedding '{self.embedding_model_tag}' non e' scaricato. "
                f"Esegui: ollama pull {self.embedding_model_tag}"
            )
        return issues


def _model_is_installed(tag: str, installed: list[str]) -> bool:
    """Confronto tollerante tra il tag configurato e i nomi restituiti da
    Ollama: '/api/tags' restituisce sempre il nome completo con la tag
    (es. 'nomic-embed-text:latest'), mentre in .env il modello puo' essere
    scritto senza ':latest' (es. 'nomic-embed-text'). Consideriamo installato
    se combacia esattamente, oppure se il tag senza ':' combacia col nome
    installato prima dei due punti (cioe' un tag implicito ':latest')."""
    tag = tag.strip()
    if not tag:
        return False
    normalized_installed = {name.strip() for name in installed}
    if tag in normalized_installed:
        return True
    if ":" not in tag:
        # tag implicito 'latest': combacia con qualsiasi 'tag:...'? No, solo
        # con 'tag:latest', che e' cio' che Ollama assegna di default.
        if f"{tag}:latest" in normalized_installed:
            return True
    return False


async def fetch_installed_models(ollama_host: str, *, timeout: float = 5.0) -> list[str] | None:
    """Restituisce i nomi dei modelli scaricati localmente, o None se Ollama
    non e' raggiungibile (diverso da lista vuota, che significa 'raggiungibile
    ma nessun modello scaricato')."""
    try:
        async with httpx.AsyncClient(base_url=ollama_host.rstrip("/"), timeout=timeout) as client:
            response = await client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            return [model["name"] for model in data.get("models", [])]
    except Exception as exc:
        logger.warning("Diagnostica: Ollama non raggiungibile su %s: %s", ollama_host, exc)
        return None


async def run_diagnostics(*, ollama_host: str, brain_model_tag: str, embedding_model_tag: str) -> DiagnosticsResult:
    installed = await fetch_installed_models(ollama_host)
    if installed is None:
        return DiagnosticsResult(
            ollama_reachable=False,
            brain_model_present=False,
            embedding_model_present=False,
            brain_model_tag=brain_model_tag,
            embedding_model_tag=embedding_model_tag,
            installed_models=[],
        )
    return DiagnosticsResult(
        ollama_reachable=True,
        brain_model_present=_model_is_installed(brain_model_tag, installed),
        embedding_model_present=_model_is_installed(embedding_model_tag, installed),
        brain_model_tag=brain_model_tag,
        embedding_model_tag=embedding_model_tag,
        installed_models=installed,
    )
