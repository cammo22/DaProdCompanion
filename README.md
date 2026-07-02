# DaProdCompanion

Companion AI desktop 100% locale: avatar, memoria multi-livello, dreaming, riconoscimento
facciale via webcam, iniziativa proattiva. Vincolo hardware: 6GB VRAM.

Architettura completa: [docs/architecture/architettura.md](docs/architecture/architettura.md)

## Stato

**Fasi 1-3 completate**: core (sandboxing + memoria SQLite + Ollama), avatar Electron (overlay
desktop + tray icon + chat testuale), TTS italiano (Kokoro). Webcam, dreaming e grafo arrivano
nelle fasi successive.

## Avvio (uso normale, dopo la prima installazione)

```powershell
cd app
npm start
```

Questo compila (se necessario) e avvia Electron, che a sua volta lancia `brain_service` e
`tts_service` come processi figli supervisionati. Per chiudere tutto: icona nella system tray
(vicino all'orologio) -> tasto destro -> Esci.

## Prima installazione

Prerequisiti: [uv](https://docs.astral.sh/uv/), Node.js/npm, Ollama in esecuzione con
`gemma4:e4b-it-qat` gia' scaricato, [eSpeak NG](https://github.com/espeak-ng/espeak-ng) installato
(`winget install eSpeak-NG.eSpeak-NG` su Windows, necessario per la sintesi vocale italiana).

```powershell
copy .env.example .env
uv sync --all-packages
cd app
npm install
npm start
```

Al primo avvio viene chiesto il nome del companion (default proposto: "Babbasone"): determina la
cartella dedicata creata su `Desktop\<nome>\`, dove vivono database, log, audio generato e (nelle
fasi successive) memorie, screenshot e volti riconosciuti — mai dentro al repo.

## Solo backend, senza interfaccia (utile per debug)

Per testare `brain_service` da riga di comando senza Electron:

```powershell
.\scripts\dev-up.ps1
```

```powershell
curl http://127.0.0.1:8770/health
curl -X POST http://127.0.0.1:8770/chat -H "Content-Type: application/json" -d "{\"message\": \"ciao\"}"
```
