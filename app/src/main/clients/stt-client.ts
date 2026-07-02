/**
 * Client REST verso stt_service: elenco microfoni disponibili (per il menu
 * Impostazioni) e mute/unmute (proxato dall'avatar).
 */

import { getConfig } from "../config";

function baseUrl(): string {
  return `http://127.0.0.1:${getConfig().sttHttpPort}`;
}

export interface MicDevice {
  index: number;
  name: string;
}

export async function listMicDevices(): Promise<MicDevice[]> {
  const res = await fetch(`${baseUrl()}/devices`);
  if (!res.ok) {
    throw new Error(`stt /devices ha risposto ${res.status}`);
  }
  const data = (await res.json()) as { devices: MicDevice[] };
  return data.devices;
}

export async function toggleMicMute(): Promise<boolean> {
  const res = await fetch(`${baseUrl()}/mic/toggle-mute`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`stt /mic/toggle-mute ha risposto ${res.status}`);
  }
  const data = (await res.json()) as { muted: boolean };
  return data.muted;
}

export async function getMicMuteState(): Promise<boolean> {
  const res = await fetch(`${baseUrl()}/mic/mute-state`);
  if (!res.ok) {
    throw new Error(`stt /mic/mute-state ha risposto ${res.status}`);
  }
  const data = (await res.json()) as { muted: boolean };
  return data.muted;
}

/** Mute legato alla riproduzione audio reale (eventi play/ended lato
 * renderer), indipendente dal mute manuale dell'utente: vedi MicMuteState
 * lato stt_service, che compone i due flag separatamente apposta per non
 * farli interferire tra loro. */
export async function setSpeakingMute(muted: boolean): Promise<void> {
  const res = await fetch(`${baseUrl()}/mic/speaking-mute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ muted }),
  });
  if (!res.ok) {
    throw new Error(`stt /mic/speaking-mute ha risposto ${res.status}`);
  }
}

/** Pulsante "registra" (push-to-talk): avvia/ferma l'accumulo manuale
 * dell'audio, inviato per intero alla fine senza bisogno del wake-word. */
export async function startRecording(): Promise<void> {
  const res = await fetch(`${baseUrl()}/recording/start`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`stt /recording/start ha risposto ${res.status}`);
  }
}

export async function stopRecording(): Promise<void> {
  const res = await fetch(`${baseUrl()}/recording/stop`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`stt /recording/stop ha risposto ${res.status}`);
  }
}

/** Pulsante "live": apre/chiude la finestra di conversazione senza dover
 * dire il nome del bot. */
export async function startLiveMode(): Promise<void> {
  const res = await fetch(`${baseUrl()}/live/start`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`stt /live/start ha risposto ${res.status}`);
  }
}

export async function stopLiveMode(): Promise<void> {
  const res = await fetch(`${baseUrl()}/live/stop`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`stt /live/stop ha risposto ${res.status}`);
  }
}

/** Calibrazione del riconoscimento del nome: varianti di trascrizione extra
 * (oltre al nome esatto e al fuzzy-match generico) che l'utente puo'
 * raccogliere osservando i log e aggiungere qui, senza riavviare stt_service. */
export async function listWakeWordVariants(): Promise<string[]> {
  const res = await fetch(`${baseUrl()}/wake-word/variants`);
  if (!res.ok) {
    throw new Error(`stt /wake-word/variants ha risposto ${res.status}`);
  }
  return ((await res.json()) as { variants: string[] }).variants;
}

export async function addWakeWordVariant(variant: string): Promise<string[]> {
  const res = await fetch(`${baseUrl()}/wake-word/variants`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ variant }),
  });
  if (!res.ok) {
    throw new Error(`stt /wake-word/variants (POST) ha risposto ${res.status}`);
  }
  return ((await res.json()) as { variants: string[] }).variants;
}

export async function removeWakeWordVariant(variant: string): Promise<string[]> {
  const res = await fetch(`${baseUrl()}/wake-word/variants/remove`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ variant }),
  });
  if (!res.ok) {
    throw new Error(`stt /wake-word/variants/remove ha risposto ${res.status}`);
  }
  return ((await res.json()) as { variants: string[] }).variants;
}

export async function testWakeWord(text: string): Promise<boolean> {
  const res = await fetch(`${baseUrl()}/wake-word/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) {
    throw new Error(`stt /wake-word/test ha risposto ${res.status}`);
  }
  return ((await res.json()) as { matches: boolean }).matches;
}
