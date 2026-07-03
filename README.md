# DaProdCompanion

Companion AI desktop 100% locale, in italiano: avatar sempre in primo piano, memoria multi-livello
con "dreaming" notturno, grafo di conoscenza esplorabile ("cervellone"), voce (wake-word,
push-to-talk, modalita' live), tool-use ristretto per il modello, e una modalita' "Quantum" in cui
il companion espande da solo il proprio grafo. Nessun dato lascia il PC: LLM, TTS e STT girano
tutti tramite Ollama e modelli locali.

Architettura di riferimento (scritta prima di iniziare, non tutta ancora attuale):
[docs/architecture/architettura.md](docs/architecture/architettura.md).

## Stato (v0.0.1)

Prima release taggata, pensata per essere provata e per raccogliere feedback — non e' un
prodotto "finito e inscatolato": manca un installer (si avvia da sorgente con `uv`/`npm`), manca
la Fase Webcam/riconoscimento facciale, e ci sono ancora bug noti in fase di rifinitura.

Quello che c'e' e funziona:

- **Core**: sandboxing filesystem obbligatorio, SQLite (WAL, `sqlite-vec` per gli embedding),
  loop di conversazione con Ollama.
- **Avatar**: overlay trasparente sempre in primo piano, stati visivi (ascolto/pensa/parla/sogna/
  sente il proprio nome), pulsanti compatti (muto, registra, live, salta, cronologia),
  trascinabile, anteprima live di quello che stai dicendo, bolla che mostra sempre sia il
  messaggio ricevuto sia la risposta.
- **Voce**: ascolto continuo con wake-word configurabile (nome del companion), finestra di
  conversazione senza dover ripetere il nome, push-to-talk, modalita' live, calibrazione del
  riconoscimento del nome dal menu Impostazioni, filtro delle allucinazioni di Whisper.
- **Memoria e dreaming**: consolidamento periodico (cron notturno, per inattivita', per
  dimensione) della memoria episodica in memoria semantica + grafo di conoscenza, sospeso
  automaticamente mentre stai parlando o registrando. Il companion annuncia (testo + voce) cosa
  ha sognato.
- **Cervellone (grafo)**: pannello con forza dei nodi personalizzabile (repulsione/attrazione),
  filtri per tipo di entita' e per nodi isolati, dimensione dei nodi in base ai collegamenti,
  timer dell'ultimo/prossimo sogno.
- **Export in markdown**: ogni entita' del grafo diventa una nota con frontmatter YAML (stile
  vault Obsidian), oltre a un diario dei sogni e una pagina "chi sono" auto-scritta dal companion.
- **Tool-use ristretto**: il modello puo' salvare una memoria al volo o interrogare il grafo
  durante la conversazione — niente esecuzione di codice, niente accesso al filesystem oltre al
  wrapper di sandboxing.
- **Modalita' Quantum**: ciclo autonomo (fino a 20 iterazioni) in cui il companion esplora e
  arricchisce da solo il proprio grafo, esclusivo con ascolto e dreaming normale.
- **Impostazioni**: nome del companion, scelta del modello Ollama da un menu popolato dai modelli
  gia' scaricati in locale, voce/velocita' TTS, microfono, calibrazione wake-word, reset completo
  della memoria (DB + vault markdown).

## Avvio (uso normale, dopo la prima installazione)

```powershell
cd app
npm start
```

Electron compila (se serve) e avvia `brain_service`, `tts_service` e `stt_service` come processi
figli supervisionati. Per chiudere tutto: icona nella system tray (vicino all'orologio) -> tasto
destro -> Esci.

## Prima installazione

Prerequisiti:

- [uv](https://docs.astral.sh/uv/) e Node.js/npm
- [Ollama](https://ollama.com/) in esecuzione, con almeno un modello per la chat scaricato (es.
  `ollama pull gemma4:e4b-it-qat`) e `ollama pull nomic-embed-text` per gli embedding
- [eSpeak NG](https://github.com/espeak-ng/espeak-ng) installato (`winget install
  eSpeak-NG.eSpeak-NG` su Windows), necessario per la sintesi vocale italiana di Kokoro

```powershell
copy .env.example .env
uv sync --all-packages
cd app
npm install
npm start
```

Al primo avvio viene chiesto il nome del companion (default proposto: "Babbasone"): determina la
cartella dedicata creata su `Desktop\<nome>\`, dove vivono database, log, audio generato, memorie
esportate in markdown e grafo — mai dentro al repo. Il modello Ollama da usare si sceglie (o si
cambia in seguito) dal menu Impostazioni, tra quelli gia' scaricati in locale.

## Solo backend, senza interfaccia (utile per debug)

```powershell
.\scripts\dev-up.ps1
```

```powershell
curl http://127.0.0.1:8770/health
curl -X POST http://127.0.0.1:8770/chat -H "Content-Type: application/json" -d "{\"message\": \"ciao\"}"
```

## Test

```powershell
uv run pytest services/brain/tests services/stt/tests shared/tests -q
cd app; npm run build
```

## Cosa manca per una versione davvero "inscatolata"

- Installer offline (electron-builder, runtime Python bundlato, niente `uv`/`npm` richiesti
  all'utente finale)
- Fase Webcam / riconoscimento facciale (mai iniziata)
- Streaming reale della sintesi vocale (oggi Kokoro sintetizza l'intera risposta prima di
  riprodurla)
