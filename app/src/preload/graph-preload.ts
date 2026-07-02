import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("graphAPI", {
  getSnapshot: () => ipcRenderer.invoke("graph:get-snapshot"),
  onUpdated: (callback: () => void): void => {
    ipcRenderer.on("graph:updated", () => callback());
  },
});
