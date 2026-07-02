import { contextBridge, ipcRenderer } from "electron";

export interface BubblePayload {
  text: string;
  usedMemory: boolean;
  suggestedDurationMs: number;
  audioUrl: string | null;
}

contextBridge.exposeInMainWorld("avatarAPI", {
  onStateChange: (callback: (state: string) => void): void => {
    ipcRenderer.on("avatar:state-changed", (_event, state: string) => callback(state));
  },
  onBubble: (callback: (payload: BubblePayload) => void): void => {
    ipcRenderer.on("avatar:bubble", (_event, payload: BubblePayload) => callback(payload));
  },
  onDreamingStart: (callback: () => void): void => {
    ipcRenderer.on("avatar:dreaming-start", () => callback());
  },
  onDreamingEnd: (callback: () => void): void => {
    ipcRenderer.on("avatar:dreaming-end", () => callback());
  },
  openChat: (): void => {
    ipcRenderer.send("avatar:open-chat");
  },
  toggleMicMute: (): Promise<boolean> => ipcRenderer.invoke("avatar:toggle-mic-mute"),
  getMicMuteState: (): Promise<boolean> => ipcRenderer.invoke("avatar:get-mic-mute-state"),
  notifySpeakingStart: (): void => ipcRenderer.send("audio:speaking-start"),
  notifySpeakingEnd: (): void => ipcRenderer.send("audio:speaking-end"),
});
