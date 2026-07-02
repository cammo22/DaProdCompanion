# Scarica i modelli Ollama richiesti dal .env corrente che non sono ancora presenti
# in locale. gemma4:e4b-it-qat / e2b-it-qat risultano gia' installati su questa
# macchina: lo script serve soprattutto per il modello di embedding (Fase 5).

$ErrorActionPreference = "Stop"

Write-Host "Verifico/scarico nomic-embed-text (memoria semantica, Fase 5)..."
ollama pull nomic-embed-text

Write-Host "Modelli disponibili:"
ollama list
