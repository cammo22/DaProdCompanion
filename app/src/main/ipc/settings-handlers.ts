/**
 * Handler IPC delle impostazioni: lettura/scrittura di un sottoinsieme
 * mirato di .env (non ogni chiave possibile: solo cio' che ha senso
 * esporre in una UI), riavvio completo dell'app per applicare le modifiche,
 * e il reset della memoria (proxati verso brain_service).
 */

import { app, ipcMain } from "electron";
import { getConfig, refreshConfig, writeEnvValues } from "../config";
import { resetAllMemory } from "../clients/brain-client";
import {
  addWakeWordVariant,
  listMicDevices,
  listWakeWordVariants,
  removeWakeWordVariant,
  testWakeWord,
  type MicDevice,
} from "../clients/stt-client";
import { listOllamaModels, type OllamaModel } from "../clients/ollama-client";

export interface SettingsPayload {
  botName: string;
  brainModelTag: string;
  ttsVoiceId: string;
  ttsSpeed: number;
  micDeviceIndex: number | null;
}

export function registerSettingsHandlers(): void {
  ipcMain.handle("settings:get", (): SettingsPayload => {
    const config = getConfig();
    return {
      botName: config.botName,
      brainModelTag: config.brainModelTag,
      ttsVoiceId: config.ttsVoiceId,
      ttsSpeed: config.ttsSpeed,
      micDeviceIndex: config.micDeviceIndex,
    };
  });

  ipcMain.handle("settings:save", (_event, payload: SettingsPayload) => {
    writeEnvValues({
      BOT_NAME: payload.botName,
      BRAIN_MODEL_TAG: payload.brainModelTag,
      TTS_VOICE_ID: payload.ttsVoiceId,
      TTS_SPEED: String(payload.ttsSpeed),
      MIC_DEVICE_INDEX: payload.micDeviceIndex !== null ? String(payload.micDeviceIndex) : "",
    });
    refreshConfig();
  });

  ipcMain.handle("settings:restart-app", () => {
    app.relaunch();
    app.exit(0);
  });

  ipcMain.handle("settings:reset-memory", () => resetAllMemory());

  ipcMain.handle("settings:list-mic-devices", async (): Promise<MicDevice[]> => {
    try {
      return await listMicDevices();
    } catch {
      // stt_service non raggiungibile (es. finestra impostazioni aperta
      // prima che il servizio sia pronto): lista vuota, non un errore fatale
      // per il resto del form.
      return [];
    }
  });

  ipcMain.handle("settings:list-ollama-models", async (): Promise<OllamaModel[]> => {
    try {
      return await listOllamaModels(getConfig().ollamaHost);
    } catch {
      // Ollama non raggiungibile (non ancora avviato, host diverso, ecc.):
      // lista vuota, il renderer mostra comunque il tag salvato come opzione.
      return [];
    }
  });

  ipcMain.handle("settings:list-wake-word-variants", async (): Promise<string[]> => {
    try {
      return await listWakeWordVariants();
    } catch {
      return [];
    }
  });

  ipcMain.handle("settings:add-wake-word-variant", (_event, variant: string) => addWakeWordVariant(variant));
  ipcMain.handle("settings:remove-wake-word-variant", (_event, variant: string) => removeWakeWordVariant(variant));
  ipcMain.handle("settings:test-wake-word", (_event, text: string) => testWakeWord(text));
}
