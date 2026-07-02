import { contextBridge, ipcRenderer } from "electron";

export interface SettingsPayload {
  botName: string;
  brainModelTag: string;
  ttsVoiceId: string;
  ttsSpeed: number;
  micDeviceIndex: number | null;
}

export interface MicDevice {
  index: number;
  name: string;
}

export interface OllamaModel {
  name: string;
}

contextBridge.exposeInMainWorld("settingsAPI", {
  get: (): Promise<SettingsPayload> => ipcRenderer.invoke("settings:get"),
  save: (payload: SettingsPayload): Promise<void> => ipcRenderer.invoke("settings:save", payload),
  restartApp: (): Promise<void> => ipcRenderer.invoke("settings:restart-app"),
  resetMemory: (): Promise<{ status: string }> => ipcRenderer.invoke("settings:reset-memory"),
  listMicDevices: (): Promise<MicDevice[]> => ipcRenderer.invoke("settings:list-mic-devices"),
  listOllamaModels: (): Promise<OllamaModel[]> => ipcRenderer.invoke("settings:list-ollama-models"),
  listWakeWordVariants: (): Promise<string[]> => ipcRenderer.invoke("settings:list-wake-word-variants"),
  addWakeWordVariant: (variant: string): Promise<string[]> => ipcRenderer.invoke("settings:add-wake-word-variant", variant),
  removeWakeWordVariant: (variant: string): Promise<string[]> =>
    ipcRenderer.invoke("settings:remove-wake-word-variant", variant),
  testWakeWord: (text: string): Promise<boolean> => ipcRenderer.invoke("settings:test-wake-word", text),
});
