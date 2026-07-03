import { contextBridge, ipcRenderer } from "electron";

export interface DreamingStatus {
  lastDreamAt: string | null;
  nextScheduledAt: string | null;
}

export interface QuantumStatus {
  active: boolean;
  iterationsDone: number;
}

contextBridge.exposeInMainWorld("graphAPI", {
  getSnapshot: () => ipcRenderer.invoke("graph:get-snapshot"),
  onUpdated: (callback: () => void): void => {
    ipcRenderer.on("graph:updated", () => callback());
  },
  triggerNow: (): Promise<{ consolidated_events: number }> => ipcRenderer.invoke("graph:trigger-now"),
  getDreamingStatus: (): Promise<DreamingStatus> => ipcRenderer.invoke("graph:get-dreaming-status"),
  startQuantum: (): Promise<QuantumStatus> => ipcRenderer.invoke("graph:start-quantum"),
  stopQuantum: (): Promise<QuantumStatus> => ipcRenderer.invoke("graph:stop-quantum"),
  getQuantumStatus: (): Promise<QuantumStatus> => ipcRenderer.invoke("graph:get-quantum-status"),
  onQuantumStatusChanged: (callback: () => void): void => {
    ipcRenderer.on("graph:quantum-status-changed", () => callback());
  },
  onQuantumInsight: (callback: (insight: string, iteration: number) => void): void => {
    ipcRenderer.on("graph:quantum-insight", (_event, payload: { insight: string; iteration: number }) =>
      callback(payload.insight, payload.iteration),
    );
  },
});
