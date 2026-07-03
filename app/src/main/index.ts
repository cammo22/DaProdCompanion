/**
 * Entry point del processo main Electron: risolve il nome del bot (onboarding
 * se serve), avvia l'avatar, avvia brain_service come processo figlio
 * supervisionato, registra gli handler IPC, gestisce lo spegnimento pulito.
 */

import { app, dialog } from "electron";
import { pathToFileURL } from "node:url";
import { isAppQuitting, markAppQuitting } from "./app-state";
import { getDiagnostics } from "./clients/brain-client";
import { getConfig, pythonRuntimeExists, refreshConfig, writeBotName } from "./config";
import { registerAudioHandlers } from "./ipc/audio-handlers";
import { registerAvatarHandlers } from "./ipc/avatar-handlers";
import { registerChatHandlers } from "./ipc/chat-handlers";
import { registerGraphHandlers } from "./ipc/graph-handlers";
import { registerSettingsHandlers } from "./ipc/settings-handlers";
import { createBrainSupervisor } from "./services/brain-service";
import { createTtsSupervisor } from "./services/tts-service";
import { createSttSupervisor } from "./services/stt-service";
import type { ProcessSupervisor } from "./services/process-supervisor";
import { BrainEventClient, type BrainEvent } from "./services/ws-client";
import {
  createAvatarWindow,
  flashReply,
  flashWakeWordDetected,
  hideDreamingBubble,
  setAvatarState,
  setListening,
  setVoiceProcessing,
  showDreamingBubble,
  showPartialTranscript,
} from "./windows/avatar-window";
import { createChatWindow, notifyNewExchange, showChatWindow } from "./windows/chat-window";
import {
  createGraphWindow,
  notifyGraphUpdated,
  notifyQuantumInsight,
  notifyQuantumStatusChanged,
  showGraphWindow,
} from "./windows/graph-window";
import { showOnboardingWindow } from "./windows/onboarding-window";
import { createSettingsWindow } from "./windows/settings-window";
import { createTray } from "./tray";

// Su macchine con GPU ibrida (iGPU + dGPU, come questa: AMD integrata + NVIDIA
// dedicata) le finestre trasparenti Electron possono finire composte sulla GPU
// sbagliata e risultare invisibili pur essendo "visibili" per Windows (HWND
// valido, IsWindowVisible=true, nessun errore in nessun log). Questo switch
// forza Chromium a preferire la GPU dedicata per tutti i processi. Va chiamato
// prima di app.whenReady().
app.commandLine.appendSwitch("force_high_performance_gpu");

const DEFAULT_BOT_NAME = "Babbasone";

let brainSupervisor: ProcessSupervisor | null = null;
let ttsSupervisor: ProcessSupervisor | null = null;
let sttSupervisor: ProcessSupervisor | null = null;
let brainEvents: BrainEventClient | null = null;

// dream-announcement e dreaming-finished arrivano dallo stesso ciclo, in
// quest'ordine (vedi consolidation.py: l'annuncio e' pubblicato nel try,
// dreaming-finished nel finally che gira sempre dopo): se dreaming-finished
// nascondesse comunque la bubble, interromperebbe subito l'annuncio appena
// mostrato da flashReply. Questo flag lo evita senza dover cambiare l'ordine
// degli eventi lato brain.
let dreamAnnouncedThisCycle = false;

function handleBrainEvent(event: BrainEvent): void {
  switch (event.type) {
    case "dreaming-started":
      showDreamingBubble();
      break;
    case "dreaming-finished":
      if (!dreamAnnouncedThisCycle) {
        hideDreamingBubble();
      }
      dreamAnnouncedThisCycle = false;
      break;
    case "dream-announcement": {
      // Il companion "racconta" cosa ha sognato, sia a voce sia in bolla:
      // stesso meccanismo di voice-reply, riusato qui.
      dreamAnnouncedThisCycle = true;
      const summary = typeof event.summary === "string" ? event.summary : "";
      const audioPath = typeof event.audio_path === "string" ? event.audio_path : null;
      const durationSeconds = typeof event.duration_seconds === "number" ? event.duration_seconds : null;
      const bubbleDurationMs = durationSeconds ? durationSeconds * 1000 + 1000 : 10000;
      const audioUrl = audioPath ? pathToFileURL(audioPath).href : null;
      flashReply(summary, false, bubbleDurationMs, audioUrl);
      break;
    }
    case "graph-updated":
      notifyGraphUpdated();
      break;
    case "listening-started":
      setListening(true);
      break;
    case "listening-finished":
      setListening(false);
      break;
    case "wake-word-detected":
      flashWakeWordDetected();
      break;
    case "voice-processing":
      setVoiceProcessing();
      break;
    case "voice-processing-failed":
      setAvatarState("idle");
      break;
    case "voice-reply": {
      // Percorso analogo a chat-handlers.ts per la chat testuale, ma qui e'
      // brain a spingere l'evento (nessuno sta aspettando una risposta HTTP,
      // vedi stt_service/brain_client.py): stessa conversione audio_path ->
      // file://, ma la riproduzione avviene nella finestra avatar, non chat.
      const userMessage = typeof event.user_message === "string" ? event.user_message : "";
      const reply = typeof event.reply === "string" ? event.reply : "";
      const audioPath = typeof event.audio_path === "string" ? event.audio_path : null;
      const durationSeconds = typeof event.duration_seconds === "number" ? event.duration_seconds : null;
      const usedMemory = Boolean(event.used_memory);
      const bubbleDurationMs = durationSeconds ? durationSeconds * 1000 + 500 : undefined;
      const audioUrl = audioPath ? pathToFileURL(audioPath).href : null;
      flashReply(reply, usedMemory, bubbleDurationMs, audioUrl, userMessage);
      // La chat testuale mostra anche gli scambi partiti dalla voce (stessa
      // conversazione, solo un altro modo di parlare), ma non ne riproduce
      // l'audio: se lo facesse, suonerebbe due volte (gia' in corso sull'avatar).
      if (userMessage) notifyNewExchange(userMessage, reply, usedMemory);
      break;
    }
    case "partial-transcript": {
      const text = typeof event.text === "string" ? event.text : "";
      showPartialTranscript(text);
      break;
    }
    case "quantum-started":
    case "quantum-finished":
      notifyQuantumStatusChanged();
      break;
    case "quantum-insight": {
      const insight = typeof event.insight === "string" ? event.insight : "";
      const iteration = typeof event.iteration === "number" ? event.iteration : 0;
      if (insight) notifyQuantumInsight(insight, iteration);
      break;
    }
    default:
      break;
  }
}

// Rete di sicurezza diagnostica: senza questi handler, un errore non catturato
// nel processo main puo' far terminare Electron senza lasciare traccia in
// nessun log applicativo (ne' brain_service ne' i nostri file di log lo
// vedrebbero, perche' non e' un problema loro).
process.on("uncaughtException", (err) => {
  console.error("[main] eccezione non gestita:", err);
});
process.on("unhandledRejection", (reason) => {
  console.error("[main] promise rifiutata senza handler:", reason);
});

async function ensureBotName(): Promise<void> {
  if (getConfig().botName) return;
  const chosen = await showOnboardingWindow(DEFAULT_BOT_NAME);
  writeBotName(chosen);
  refreshConfig();
}

app.whenReady().then(async () => {
  console.log("[main] app pronta, risolvo il nome del bot...");
  await ensureBotName();

  console.log("[main] creo le finestre...");
  createAvatarWindow();
  createChatWindow();
  createGraphWindow();
  createSettingsWindow();
  createTray(getConfig().botName);
  registerAvatarHandlers();
  registerChatHandlers();
  registerGraphHandlers();
  registerSettingsHandlers();
  registerAudioHandlers();

  // Tutte e tre le finestre principali visibili di default (avatar, chat,
  // cervellone), in primo piano: l'utente abbassa quella che non gli serve
  // invece di doverle aprire a mano una per una.
  showChatWindow();
  showGraphWindow();

  setAvatarState("thinking");

  // Se il runtime Python non esiste al percorso atteso, avviare i supervisori
  // e' inutile: falliranno tutti con un errore criptico. Diamo subito il
  // messaggio giusto a seconda del contesto (eseguibile portable senza la
  // variabile d'ambiente, oppure checkout di sviluppo senza 'uv sync').
  if (!pythonRuntimeExists()) {
    setAvatarState("idle");
    const detail = app.isPackaged
      ? "L'eseguibile portable ha bisogno di sapere dove si trova il checkout del progetto " +
        "(dove vivono .env e .venv). Imposta la variabile d'ambiente DAPRODCOMPANION_ROOT sul " +
        "percorso di quel checkout e riavvia. Nota: questa versione non include ancora Python/" +
        "Ollama al suo interno, vanno installati a parte (vedi README)."
      : "Non trovo l'ambiente Python (.venv). Dalla radice del progetto esegui:\n\n" +
        "  uv sync --all-packages\n\ne riavvia il companion.";
    dialog.showMessageBox({
      type: "error",
      title: "DaProdCompanion — ambiente non pronto",
      message: "Manca l'ambiente Python necessario per avviare il companion.",
      detail,
    });
    return;
  }

  console.log("[main] avvio brain_service, tts_service e stt_service...");
  brainSupervisor = createBrainSupervisor();
  ttsSupervisor = createTtsSupervisor();
  sttSupervisor = createSttSupervisor();
  const serviceNames = ["brain_service", "tts_service", "stt_service"];
  const results = await Promise.allSettled([
    brainSupervisor.start(),
    ttsSupervisor.start(),
    sttSupervisor.start(),
  ]);
  let brainReady = false;
  results.forEach((result, i) => {
    const name = serviceNames[i];
    if (result.status === "fulfilled") {
      console.log(`[main] ${name} pronto.`);
      if (i === 0) brainReady = true;
    } else {
      console.error(`[main] ${name} non si e' avviato:`, result.reason);
    }
  });
  setAvatarState("idle");

  if (brainReady) {
    const { brainHttpPort } = getConfig();
    brainEvents = new BrainEventClient(`ws://127.0.0.1:${brainHttpPort}/ws`, handleBrainEvent);
    brainEvents.connect();

    // Setup iniziale: brain risponde /health anche se Ollama non gira o il
    // modello non e' scaricato, ma in quel caso la prima chat fallirebbe con
    // un errore incomprensibile. Controlliamo i prerequisiti a monte e, se
    // manca qualcosa, lo diciamo chiaramente all'utente con l'azione precisa
    // da fare (es. "esegui ollama pull ..."), invece di lasciarlo scoprire
    // dal fallimento silenzioso.
    await checkPrerequisites();
  } else {
    dialog.showMessageBox({
      type: "error",
      title: "DaProdCompanion",
      message: "Il cervello del companion (brain_service) non si e' avviato.",
      detail:
        "Controlla che Python e le dipendenze siano installate correttamente " +
        "(uv sync --all-packages) e riavvia. I log dettagliati sono nella cartella " +
        "'logs' dentro la cartella del companion sul Desktop.",
    });
  }
}).catch((err) => {
  console.error("[main] errore durante l'avvio:", err);
});

async function checkPrerequisites(): Promise<void> {
  try {
    const diagnostics = await getDiagnostics();
    if (diagnostics.ok) return;
    await dialog.showMessageBox({
      type: "warning",
      title: "DaProdCompanion — configurazione da completare",
      message: "Manca qualcosa perche' il companion funzioni:",
      detail:
        diagnostics.problems.map((p) => `• ${p}`).join("\n\n") +
        "\n\nRisolvi questi punti e riavvia il companion. " +
        "Il modello per la conversazione si puo' anche cambiare dalle Impostazioni, " +
        "scegliendone uno gia' scaricato.",
    });
  } catch (err) {
    // La diagnostica e' best-effort: se fallisce (es. brain e' appena caduto)
    // non blocchiamo l'avvio ne' mostriamo un errore fuorviante.
    console.warn("[main] diagnostica prerequisiti non riuscita:", err);
  }
}

app.on("window-all-closed", () => {
  // Con isAppQuitting() gestito correttamente (vedi chat-window.ts), questo
  // scatta solo a spegnimento gia' in corso: la chiusura del processo procede
  // da sola una volta che before-quit ha finito la pulizia sotto.
});

app.on("before-quit", async (event) => {
  if (isAppQuitting()) return;
  event.preventDefault();
  markAppQuitting();

  brainEvents?.close();
  brainEvents = null;

  await Promise.allSettled([
    brainSupervisor?.stop() ?? Promise.resolve(),
    ttsSupervisor?.stop() ?? Promise.resolve(),
    sttSupervisor?.stop() ?? Promise.resolve(),
  ]);
  brainSupervisor = null;
  ttsSupervisor = null;
  sttSupervisor = null;
  app.quit();
});
