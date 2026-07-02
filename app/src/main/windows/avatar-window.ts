/**
 * Finestra overlay dell'avatar: senza bordi, trasparente, sempre in primo
 * piano. Placeholder CSS (nessun asset grafico reale disponibile): un "blob"
 * animato che cambia colore/animazione per stato.
 *
 * Il timer di auto-nascondimento della bubble di testo vive nel renderer
 * (non qui), perche' deve mettersi in pausa quando il mouse ci passa sopra
 * (richiesto dall'utente) — coordinarlo da qui significherebbe far viaggiare
 * gli eventi di hover del renderer fino al main process e ritorno senza
 * bisogno. Il cambio di colore/stato dell'avatar invece resta temporizzato
 * da qui, in modo semplice: puo' tornare a "idle" anche mentre la bubble
 * resta visibile per l'hover, ed e' un comportamento voluto, non un bug.
 */

import { BrowserWindow, screen } from "electron";
import path from "node:path";

export type AvatarState = "idle" | "listening" | "wake-word" | "thinking" | "speaking" | "dreaming";

let avatarWindow: BrowserWindow | null = null;
let idleTimer: ReturnType<typeof setTimeout> | null = null;

export function createAvatarWindow(): BrowserWindow {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;

  avatarWindow = new BrowserWindow({
    width: 480,
    height: 760,
    x: width - 500,
    y: Math.max(0, height - 800), // su schermi bassi non deve finire sopra il bordo superiore
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: true,
    hasShadow: false,
    webPreferences: {
      preload: path.join(__dirname, "../../preload/avatar-preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  avatarWindow.loadFile(path.join(__dirname, "../../../src/renderer/avatar/index.html"));

  avatarWindow.on("closed", () => {
    avatarWindow = null;
  });

  return avatarWindow;
}

export function setAvatarState(state: AvatarState): void {
  avatarWindow?.webContents.send("avatar:state-changed", state);
}

/** Bubble di risposta della chat: nascondimento con timer gestito dal
 * renderer (si mette in pausa se il mouse ci passa sopra). 'audioUrl' e'
 * usato solo dal percorso vocale (vedi handleBrainEvent in index.ts): la
 * chat testuale riproduce l'audio nella propria finestra, non qui, quindi lo
 * lascia a undefined e il renderer non tenta nessuna riproduzione doppia. */
export function flashReply(
  text: string,
  usedMemory: boolean,
  suggestedDurationMs = 8000,
  audioUrl?: string | null,
  userMessage?: string | null,
): void {
  if (idleTimer) clearTimeout(idleTimer);
  setAvatarState("speaking");
  avatarWindow?.webContents.send("avatar:bubble", {
    text,
    usedMemory,
    suggestedDurationMs,
    audioUrl: audioUrl ?? null,
    userMessage: userMessage ?? null,
  });
  idleTimer = setTimeout(() => {
    setAvatarState("idle");
  }, suggestedDurationMs);
}

/** Anteprima di quello che l'utente sta dicendo, aggiornata man mano che
 * arrivano nuovi pezzi trascritti (vedi evento partial-transcript, inoltrato
 * da VoicePipeline.on_partial_transcript). Testo vuoto = nascondila: e' cosi'
 * che stt segnala "sto per inviare il messaggio vero", non un errore. */
export function showPartialTranscript(text: string): void {
  avatarWindow?.webContents.send("avatar:partial-transcript", text);
}

/** Stato "in ascolto": segue esattamente il microfono (vedi eventi
 * listening-started/finished inoltrati da stt_service tramite brain), non un
 * timer stimato — stessa logica di showDreamingBubble/hideDreamingBubble. */
export function setListening(active: boolean): void {
  if (idleTimer) clearTimeout(idleTimer);
  setAvatarState(active ? "listening" : "idle");
}

/** Flash rosso: wake-word riconosciuto (vedi on_wake_word in VoicePipeline ->
 * evento wake-word-detected). Timeout di auto-ripristino proprio (non solo
 * "thinking" successivo), perche' se la chiamata a brain fallisse a livello
 * di rete (non solo a livello LLM, gia' coperto da voice-processing-failed)
 * l'avatar resterebbe rosso per sempre senza questo timer. */
export function flashWakeWordDetected(): void {
  if (idleTimer) clearTimeout(idleTimer);
  setAvatarState("wake-word");
  idleTimer = setTimeout(() => {
    setAvatarState("idle");
  }, 3000);
}

/** Stato "sta pensando" durante il percorso vocale (tra l'invio a brain e
 * l'arrivo dell'evento voice-reply). Per la chat testuale lo stato
 * "thinking" e' gia' gestito direttamente da chat-handlers.ts. */
export function setVoiceProcessing(): void {
  if (idleTimer) clearTimeout(idleTimer);
  setAvatarState("thinking");
}

/** Bubble "Sognando...": a differenza di flashReply, segue esattamente lo
 * stato reale del dreaming (mostrata/nascosta dagli eventi dreaming-started/
 * dreaming-finished), non un timer stimato. */
export function showDreamingBubble(): void {
  if (idleTimer) clearTimeout(idleTimer);
  setAvatarState("dreaming");
  avatarWindow?.webContents.send("avatar:dreaming-start");
}

export function hideDreamingBubble(): void {
  setAvatarState("idle");
  avatarWindow?.webContents.send("avatar:dreaming-end");
}

export function getAvatarWindow(): BrowserWindow | null {
  return avatarWindow;
}
