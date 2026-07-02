/**
 * Handler IPC delle impostazioni: lettura/scrittura di un sottoinsieme
 * mirato di .env (non ogni chiave possibile: solo cio' che ha senso
 * esporre in una UI), riavvio completo dell'app per applicare le modifiche,
 * e il reset della memoria (proxati verso brain_service).
 */

import { app, ipcMain } from "electron";
import { getConfig, refreshConfig, writeEnvValues } from "../config";
import { resetAllMemory } from "../clients/brain-client";
import { listMicDevices, type MicDevice } from "../clients/stt-client";

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
}
