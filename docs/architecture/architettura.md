# Architettura DaProdCompanion — Proposta di struttura cartelle/moduli (Fase 0, nessun codice)

## Contesto

Stai costruendo un companion AI desktop 100% locale (avatar, memoria multi-livello, dreaming,
riconoscimento facciale, iniziativa proattiva), vincolato a 6GB di VRAM. Questo e' lo **step 0**
richiesto esplicitamente prima di scrivere qualunque riga di codice: una proposta di struttura di
cartelle/moduli per il monorepo (Electron + processi Python separati), da approvare prima di
passare alla Fase 1 (core: sandboxing + SQLite + loop di conversazione base).

Prima di proporre la struttura ho verificato l'ambiente reale (non ho dato per scontato nulla,
compresi i nomi/tag dei modelli che sono successivi al mio knowledge cutoff) ed eseguito una misura
empirica di VRAM sulla GPU, dato che il budget di 6GB e' il vincolo piu' critico dell'intero
progetto.

## Cosa e' stato verificato

- **Ollama 0.31.1** gia' installato e attivo. Tra i modelli gia' scaricati: `gemma4:e4b-it-qat`
  (6.1GB su disco) e `gemma4:e2b-it-qat` (4.3GB su disco).
- **`ollama show gemma4:e4b-it-qat`**: architettura `gemma4`, **7.5B parametri**, **context length
  massima 131072 token** (quindi 32k-64k e' ampiamente supportato), capacita'
  completion+vision+audio+tools+thinking, quantizzazione Q4_0. `e2b-it-qat`: 4.6B parametri, stessa
  context length massima.
- **GPU reale**: NVIDIA RTX 4060 con **8188 MiB (~8GB) VRAM**, non 6GB. Il vincolo di 6GB dato dal
  committente e' quindi un margine di sicurezza auto-imposto, non il limite fisico della scheda.
  RAM di sistema: ~64GB, quindi CPU/RAM non sono un vincolo, solo la VRAM lo e'.
- **Misura empirica reale di VRAM** (caricamento via API locale Ollama, controllo con `ollama ps`):
  `gemma4:e4b-it-qat` occupa **~3.2GB VRAM al 100% su GPU sia a num_ctx=32768 sia a num_ctx=65536**
  (nessuno spill su CPU). `gemma4:e2b-it-qat` occupa ~1.9GB a 32768. Test con prompt minimo: da
  ripetere con una conversazione reale lunga (~30k token) prima di fidarsi del numero a pieno
  carico.
- **Kokoro-82M**: conferma supporto italiano (1 voce femminile `if_*`, 1 voce maschile `im_*`), 82M
  parametri, adatto a girare CPU-only.
- **InsightFace buffalo_s**: variante pensata per edge/mobile a risorse limitate, coerente con
  l'uso CPU-only proposto.
- **sqlite-vec**: estensione attivamente mantenuta, standard de facto attuale (ha soppiantato
  sqlite-vss), release recente v0.1.7. Compatibile con SQLite 3.50.4 incluso in Python 3.14.6.
- Strumenti disponibili: Python 3.14.6, uv 0.11.26, Node v26.3.0, npm 11.16.0, pnpm 11.9.0,
  git 2.54.0.

## Verdetto budget VRAM (6GB)

| Componente | VRAM stimata | Note |
|---|---|---|
| `gemma4:e4b-it-qat` residente (brain + vision) | ~3.2-4GB | Misurato; da confermare a pieno carico |
| `nomic-embed-text` (a scatti, retrieval/dreaming) | <0.5GB | Pullato in Fase 1, usato dalla Fase 5 |
| Kokoro TTS | 0GB | Forzato CPU-only |
| InsightFace buffalo_s | 0GB | Forzato CPU-only |
| Overhead Electron (overlay + pannello grafo) | ~0.2-0.4GB | Compositing GPU di Chromium |
| **Totale stimato** | **~4-5GB su 6GB dichiarati** (8GB hardware reali) | Margine ragionevole |

`num_ctx` di partenza: **32768** (non 65536), default prudente confermato dall'utente, modificabile
via `.env` senza toccare codice. `gemma4:e2b-it-qat` resta il fallback immediato in caso di
pressione VRAM sotto carico reale.

## Struttura di cartelle

```
DaProdCompanion/
├── app/                                  # Electron: main + renderer + preload (Fase 2+)
├── services/
│   ├── brain/                            # orchestrazione LLM, memoria, dreaming, grafo
│   ├── webcam/                           # livello 1 (always-on) + livello 2 (a scatti) — Fase 4
│   └── tts/                              # Kokoro, coda audio — Fase 3
├── shared/                               # pacchetto Python condiviso (sandbox, config, db)
├── docs/architecture/                    # questo documento
├── scripts/                              # helper di sviluppo (dev-up.ps1, pull-models.ps1)
├── .env.example
├── pyproject.toml                        # root workspace uv
└── README.md
```

Dettaglio completo di ogni modulo, contratto IPC, schema SQLite e decisioni architetturali nella
cronologia del progetto (sandbox filesystem, concorrenza SQLite, lifecycle processi Electron,
ambiente uv, config condivisa). Questo file e' la sintesi persistita nel repo; si aggiorna ad ogni
fase con le decisioni via via prese.

## Dove vive il database

Il companion salva **tutto** (database, log, memorie, screenshot, embedding facciali, file del
grafo) sotto `SANDBOX_ROOT` (default `%USERPROFILE%\Desktop\<BOT_NAME>\`), **mai** dentro l'albero
del repo. Repo (codice) e sandbox (dati) restano completamente separati.

```
%USERPROFILE%\Desktop\<BOT_NAME>\
├── db/companion.db                       # unico file SQLite (episodica+semantica+grafo+volti+audit)
├── logs/{brain,webcam,tts}.log
├── screenshots/
├── faces/
├── audio_cache/
└── graph_exports/
```

## Contratto di comunicazione tra processi (IPC)

Porte bind solo su `127.0.0.1`: brain `8770` (HTTP+WS), webcam `8771` (solo health), tts `8772`,
Ollama `11434`. Webcam e tts non parlano mai direttamente con Electron, solo con brain (unico
punto di verita' dello stato applicativo).

## Schema SQLite (tabelle)

`episodic_events`, `semantic_memories`, `semantic_memories_vec` (virtuale sqlite-vec),
`graph_nodes`, `graph_edges`, `known_people`, `face_embeddings`, `sandbox_access_log`,
`schema_migrations`. Definite in `shared/src/companion_shared/db/migrations/0001_initial.sql`.

## Corrispondenza con le fasi (ordine aggiornato dall'utente dopo la Fase 3)

Ordine originale: Core, Avatar, TTS, Webcam, Dreaming, Grafo. L'utente ha chiesto di anticipare
Dreaming e Grafo prima di Webcam, e di intercalare Voce ed estensione-cervellone rispettando la
dipendenza (l'estensione ha bisogno della voce gia' funzionante per avere qualcosa da trascrivere).
Ordine effettivo:

1. **Core** (fatto): `shared/` completo + `services/brain/` (senza dreaming/graph/proactive).
2. **Avatar Electron** (fatto): `app/`, supervisore gestisce brain.
3. **TTS** (fatto): `services/tts/`, `brain -> tts` sincrono nel `/chat`.
4. **Dreaming**: `brain/dreaming/`, popola `semantic_memories`/`semantic_memories_vec`, retrieval
   nella conversazione.
5. **Grafo**: scrittura `graph_nodes`/`graph_edges` dal dreaming, poi pannello
   `app/renderer/graph/` (react-force-graph).
6. **Input vocale**: `services/stt/` (faster-whisper), ascolto continuo, risponde solo se sente il
   proprio nome (wake-word gating pre-LLM).
7. **Estensione cervellone**: trascrizione ambientale periodica -> riassunto -> nodi/archi nel
   grafo, stessa logica di consolidamento del dreaming ma innescata dalla trascrizione vocale.
8. **Webcam/InsightFace**: `services/webcam/`, `webcam -> brain`.
9. **Installer offline (.exe)**: ultimo passo, bundling Electron+Python (Ollama/modelli restano
   prerequisito esterno, vedi sezione sopra).

## Requisiti aggiuntivi (raccolti dopo la Fase 1, da tenere presenti nelle fasi successive)

Non ancora implementati, ma l'architettura non deve chiudere le porte a nessuno di questi:

- **Installer offline (.exe)**: "alla fine" del progetto (esplicitamente posticipato dall'utente).
  Electron si pacchettizza con `electron-builder` (gia' previsto in `app/electron-builder.yml`).
  Il punto aperto e' cosa fare dei servizi Python: l'ipotesi di lavoro e' bundlare un runtime
  Python + dipendenze dentro l'installer (es. via PyInstaller o un Python embeddable), mentre
  **Ollama e i modelli restano un prerequisito esterno** (installer di più GB con i pesi dei
  modelli inclusi non e' realistico: `gemma4:e4b-it-qat` da solo pesa 6.1GB). Da confermare con
  l'utente quando si arriva davvero alla fase di packaging.
- **Nome del bot scelto in-app**: default "Babbasone", sempre modificabile dall'utente (non solo
  al primo avvio). Sostituisce/affianca il prompt da terminale della Fase 1 con una schermata di
  onboarding Electron (Fase 2).
- **Input vocale con wake-word**: dopo la chat testuale (Fase 2), predisporre un quarto servizio
  `services/stt/` (faster-whisper, gia' previsto come "slot futuro" nel piano originale). Ascolto
  del microfono sempre attivo, ma il companion genera una risposta solo se riconosce il proprio
  nome nella trascrizione (gating pre-LLM, stesso principio dei trigger economici del comportamento
  proattivo — non ogni frase captata deve arrivare a Ollama).
- **Pipeline "cervellone"**: nome scelto dall'utente per il knowledge graph (Fase 6). Va esteso
  oltre la sola fonte "dreaming da memoria episodica": periodicamente, l'audio ambientale
  trascritto viene riassunto (anche se non sembra rilevante sul momento) e confluisce come nuovi
  nodi/archi in `graph_nodes`/`graph_edges`, con la stessa logica di consolidamento del dreaming
  ma innescata dalla trascrizione invece che dalla sola conversazione diretta.
