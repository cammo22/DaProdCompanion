import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("chatAPI", {
  sendMessage: (message: string): Promise<{ reply: string; audioUrl: string | null }> =>
    ipcRenderer.invoke("chat:send", message),
  notifySpeakingStart: (): void => ipcRenderer.send("audio:speaking-start"),
  notifySpeakingEnd: (): void => ipcRenderer.send("audio:speaking-end"),
});
