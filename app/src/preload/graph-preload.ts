import { contextBridge, ipcRenderer } from "electron";

export interface DreamingStatus {
  lastDreamAt: string | null;
  nextScheduledAt: string | null;
}

contextBridge.exposeInMainWorld("graphAPI", {
  getSnapshot: () => ipcRenderer.invoke("graph:get-snapshot"),
  onUpdated: (callback: () => void): void => {
    ipcRenderer.on("graph:updated", () => callback());
  },
  triggerNow: (): Promise<{ consolidated_events: number }> => ipcRenderer.invoke("graph:trigger-now"),
  getDreamingStatus: (): Promise<DreamingStatus> => ipcRenderer.invoke("graph:get-dreaming-status"),
});
