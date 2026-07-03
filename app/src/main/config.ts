/**
 * Configurazione condivisa letta dall'unico .env alla radice del repo (stessa
 * fonte di verita' di companion_shared.config.settings lato Python). Espone
 * getConfig()/refreshConfig() invece di un oggetto statico esportato: dopo
 * l'onboarding scriviamo un nuovo BOT_NAME nel file e serve poter rileggere il
 * valore aggiornato senza dubbi di binding statico tra moduli.
 */

import { app } from "electron";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import dotenv from "dotenv";

// In sviluppo, app.getAppPath() e' la cartella app/ dentro il checkout del
// repo, quindi ".." e' la radice giusta. Una volta impacchettato con
// electron-builder, app.getAppPath() punta invece dentro le risorse
// dell'installazione (es. "resources/app.asar"), completamente separate da
// dove vivono realmente .env/.venv/i servizi Python — per quel caso serve un
// override esplicito, non c'e' modo di dedurlo automaticamente.
export const REPO_ROOT = process.env.DAPRODCOMPANION_ROOT ?? path.resolve(app.getAppPath(), "..");
export const ENV_FILE = path.join(REPO_ROOT, ".env");

export interface CompanionConfig {
  botName: string;
  ollamaHost: string;
  brainModelTag: string;
  ttsVoiceId: string;
  ttsSpeed: number;
  micDeviceIndex: number | null;
  brainHttpPort: number;
  webcamHttpPort: number;
  ttsHttpPort: number;
  sttHttpPort: number;
  logLevel: string;
}

let cached: CompanionConfig | null = null;

function readConfig(): CompanionConfig {
  const parsed = fs.existsSync(ENV_FILE) ? dotenv.parse(fs.readFileSync(ENV_FILE)) : {};
  return {
    botName: parsed.BOT_NAME ?? "",
    ollamaHost: parsed.OLLAMA_HOST ?? "http://127.0.0.1:11434",
    brainModelTag: parsed.BRAIN_MODEL_TAG ?? "gemma4:e4b-it-qat",
    ttsVoiceId: parsed.TTS_VOICE_ID ?? "if_sara",
    ttsSpeed: Number(parsed.TTS_SPEED ?? 1.15),
    // "" (o assente) = dispositivo di ingresso predefinito di sistema. Da non
    // confondere con Number("") === 0, che sarebbe un indice valido diverso.
    micDeviceIndex: parsed.MIC_DEVICE_INDEX ? Number(parsed.MIC_DEVICE_INDEX) : null,
    brainHttpPort: Number(parsed.BRAIN_HTTP_PORT ?? 8770),
    webcamHttpPort: Number(parsed.WEBCAM_HTTP_PORT ?? 8771),
    ttsHttpPort: Number(parsed.TTS_HTTP_PORT ?? 8772),
    sttHttpPort: Number(parsed.STT_HTTP_PORT ?? 8773),
    logLevel: parsed.LOG_LEVEL ?? "INFO",
  };
}

export function getConfig(): CompanionConfig {
  if (!cached) cached = readConfig();
  return cached;
}

export function refreshConfig(): CompanionConfig {
  cached = readConfig();
  return cached;
}

export function resolvedSandboxRoot(botName: string): string {
  return path.join(os.homedir(), "Desktop", botName);
}

export function pythonExecutablePath(): string {
  // In sviluppo il venv uv condiviso vive alla radice del repo. In fase di
  // packaging (installer offline, richiesto dall'utente ma posticipato "alla
  // fine") questo percorso andra' aggiornato per puntare al runtime Python
  // bundlato dentro l'app installata: vedi nota "Installer offline" in
  // docs/architecture/architettura.md.
  return path.join(REPO_ROOT, ".venv", "Scripts", "python.exe");
}

/** True se il runtime Python atteso (il venv uv) esiste davvero al percorso
 * risolto: usato all'avvio per dare un messaggio d'errore mirato quando
 * l'eseguibile portable viene lanciato senza DAPRODCOMPANION_ROOT (quindi
 * REPO_ROOT punta dentro le risorse dell'app, dove il venv non c'e'). */
export function pythonRuntimeExists(): boolean {
  return fs.existsSync(pythonExecutablePath());
}

/** Scrive/aggiorna piu' chiavi in .env in un solo passaggio: sostituisce le
 * righe KEY= gia' presenti, aggiunge in coda quelle mancanti. Stessa logica
 * (per una chiave sola) di companion_shared.config.first_run._write_bot_name
 * lato Python. */
export function writeEnvValues(updates: Record<string, string>): void {
  const lines = fs.existsSync(ENV_FILE) ? fs.readFileSync(ENV_FILE, "utf-8").split(/\r?\n/) : [];
  const remaining = new Map(Object.entries(updates));

  const rewritten = lines.map((line) => {
    const key = line.split("=")[0]?.trim();
    if (key && remaining.has(key)) {
      const value = remaining.get(key) as string;
      remaining.delete(key);
      return `${key}=${value}`;
    }
    return line;
  });

  for (const [key, value] of remaining) {
    rewritten.push(`${key}=${value}`);
  }

  fs.writeFileSync(ENV_FILE, rewritten.join("\n") + "\n", "utf-8");
}

export function writeBotName(name: string): void {
  writeEnvValues({ BOT_NAME: name });
}
