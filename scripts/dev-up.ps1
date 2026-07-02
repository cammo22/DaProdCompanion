# Avvia brain_service in modalita' sviluppo, fuori da Electron (utile finche' non
# esiste ancora un supervisore Electron che lo gestisca al posto nostro, cioe' fino
# alla Fase 2). Va eseguito dalla radice del repo.

$ErrorActionPreference = "Stop"

Write-Host "Sincronizzo le dipendenze (uv sync --all-packages)..."
# --all-packages e' necessario: la root della workspace non ha dipendenze proprie,
# senza questo flag `uv sync` installerebbe solo la root (cioe' niente).
uv sync --all-packages

if (-not (Test-Path ".env")) {
    Write-Host "Nessun .env trovato: lo creo da .env.example"
    Copy-Item ".env.example" ".env"
}

Write-Host "Avvio brain_service su 127.0.0.1..."
uv run --package brain-service python -m brain_service
