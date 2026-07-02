import { contextBridge, ipcRenderer } from "electron";

export interface BubblePayload {
  text: string;
  usedMemory: boolean;
  suggestedDurationMs: number;
  audioUrl: string | null;
  userMessage: string | null;
}

export interface HistoryTurn {
  id: number;
  eventType: "user_message" | "bot_reply";
  content: string;
  createdAt: string;
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
  onPartialTranscript: (callback: (text: string) => void): void => {
    ipcRenderer.on("avatar:partial-transcript", (_event, text: string) => callback(text));
  },
  openChat: (): void => {
    ipcRenderer.send("avatar:open-chat");
  },
  toggleMicMute: (): Promise<boolean> => ipcRenderer.invoke("avatar:toggle-mic-mute"),
  getMicMuteState: (): Promise<boolean> => ipcRenderer.invoke("avatar:get-mic-mute-state"),
  notifySpeakingStart: (): void => ipcRenderer.send("audio:speaking-start"),
  notifySpeakingEnd: (): void => ipcRenderer.send("audio:speaking-end"),
  startRecording: (): Promise<void> => ipcRenderer.invoke("avatar:start-recording"),
  stopRecording: (): Promise<void> => ipcRenderer.invoke("avatar:stop-recording"),
  startLiveMode: (): Promise<void> => ipcRenderer.invoke("avatar:start-live-mode"),
  stopLiveMode: (): Promise<void> => ipcRenderer.invoke("avatar:stop-live-mode"),
  getHistory: (): Promise<HistoryTurn[]> => ipcRenderer.invoke("avatar:get-history"),
});
