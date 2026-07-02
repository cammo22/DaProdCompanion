/**
 * Entry point del processo main Electron: risolve il nome del bot (onboarding
 * se serve), avvia l'avatar, avvia brain_service come processo figlio
 * supervisionato, registra gli handler IPC, gestisce lo spegnimento pulito.
 */

import { app } from "electron";
import { pathToFileURL } from "node:url";
import { isAppQuitting, markAppQuitting } from "./app-state";
import { getConfig, refreshConfig, writeBotName } from "./config";
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
  hideDreamingBubble,
  setAvatarState,
  setListening,
  setVoiceProcessing,
  showDreamingBubble,
} from "./windows/avatar-window";
import { createChatWindow } from "./windows/chat-window";
import { createGraphWindow, notifyGraphUpdated } from "./windows/graph-window";
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

function handleBrainEvent(event: BrainEvent): void {
  switch (event.type) {
    case "dreaming-started":
      showDreamingBubble();
      break;
    case "dreaming-finished":
      hideDreamingBubble();
      break;
    case "graph-updated":
      notifyGraphUpdated();
      break;
    case "listening-started":
      setListening(true);
      break;
    case "listening-finished":
      setListening(false);
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
      const reply = typeof event.reply === "string" ? event.reply : "";
      const audioPath = typeof event.audio_path === "string" ? event.audio_path : null;
      const durationSeconds = typeof event.duration_seconds === "number" ? event.duration_seconds : null;
      const usedMemory = Boolean(event.used_memory);
      const bubbleDurationMs = durationSeconds ? durationSeconds * 1000 + 500 : undefined;
      const audioUrl = audioPath ? pathToFileURL(audioPath).href : null;
      flashReply(reply, usedMemory, bubbleDurationMs, audioUrl);
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

  setAvatarState("thinking");
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
  }
}).catch((err) => {
  console.error("[main] errore durante l'avvio:", err);
});

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
