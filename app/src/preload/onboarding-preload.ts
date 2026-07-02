import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("onboardingAPI", {
  getDefaultName: (): Promise<string> => ipcRenderer.invoke("onboarding:get-default-name"),
  submitName: (name: string): Promise<void> => ipcRenderer.invoke("onboarding:submit-name", name),
});
