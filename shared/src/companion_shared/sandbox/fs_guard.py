"""
Wrapper di sandboxing filesystem — punto di accesso obbligato per ogni operazione su
file da parte di qualunque servizio del companion. Nessuna eccezione: nessun modulo
deve toccare il filesystem reale bypassando resolve_and_check()/open_sandboxed(),
nemmeno per comodita' di debug.
"""

from __future__ import annotations

from pathlib import Path
from typing import IO

from . import audit_log, policy


class SandboxViolation(PermissionError):
    """Sollevata quando un percorso richiesto e' fuori dalla sandbox e non e' whitelistato."""


class FilesystemGuard:
    def __init__(self, sandbox_root: Path, *, service: str, log_dir: Path | None = None) -> None:
        self.sandbox_root = sandbox_root.resolve()
        self.service = service
        self.log_dir = (log_dir or (self.sandbox_root / "logs")).resolve()
        self.sandbox_root.mkdir(parents=True, exist_ok=True)

    def resolve_and_check(self, requested_path: str | Path, *, purpose: str = "") -> Path:
        """Risolve 'requested_path' in un percorso assoluto e verifica che sia dentro
        sandbox_root oppure esplicitamente whitelistato (segue i symlink, cosi' un link
        dentro la sandbox che punta fuori viene comunque bloccato). Logga sempre il
        tentativo, consentito o negato. Solleva SandboxViolation se non e' permesso."""
        candidate = Path(requested_path)
        if not candidate.is_absolute():
            candidate = self.sandbox_root / candidate
        resolved = candidate.resolve()

        inside_sandbox = resolved == self.sandbox_root or self.sandbox_root in resolved.parents
        whitelisted = not inside_sandbox and policy.is_whitelisted(self.sandbox_root, resolved)
        allowed = inside_sandbox or whitelisted

        if inside_sandbox:
            reason = purpose or "dentro sandbox"
        elif whitelisted:
            reason = purpose or "whitelist"
        else:
            reason = purpose or "fuori sandbox, non autorizzato"

        audit_log.record(
            log_dir=self.log_dir,
            service=self.service,
            requested_path=str(resolved),
            allowed=allowed,
            reason=reason,
        )

        if not allowed:
            raise SandboxViolation(
                f"Accesso negato: '{resolved}' e' fuori da {self.sandbox_root} e non e' whitelistato. "
                f"Usa companion_shared.sandbox.policy.add_entry() per autorizzarlo esplicitamente."
            )
        return resolved

    def open_sandboxed(self, requested_path: str | Path, mode: str = "r", *, purpose: str = "", **kwargs) -> IO:
        """Apre un file passando prima per resolve_and_check(). Da preferire a
        resolve_and_check() + open() separati, per evitare che i due percorsi divergano."""
        resolved = self.resolve_and_check(requested_path, purpose=purpose)
        if any(m in mode for m in ("w", "a", "x", "+")):
            resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved.open(mode, **kwargs)

    def delete_sandboxed(self, requested_path: str | Path, *, purpose: str = "") -> None:
        """Cancella un file o una cartella (ricorsivamente) passando prima da
        resolve_and_check(), come open_sandboxed(). Non fallisce se il
        percorso non esiste gia': cancellare qualcosa di gia' assente e' un
        no-op accettabile per i chiamanti (es. reset di dati mai creati)."""
        import shutil

        resolved = self.resolve_and_check(requested_path, purpose=purpose)
        if resolved.is_dir():
            shutil.rmtree(resolved, ignore_errors=True)
        elif resolved.exists():
            resolved.unlink()
