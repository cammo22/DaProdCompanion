import { contextBridge, ipcRenderer } from "electron";

export interface ConversationTurn {
  id: number;
  eventType: "user_message" | "bot_reply";
  content: string;
  createdAt: string;
}

export interface NewExchangePayload {
  userMessage: string;
  reply: string;
  usedMemory: boolean;
}

contextBridge.exposeInMainWorld("chatAPI", {
  sendMessage: (message: string): Promise<{ reply: string; audioUrl: string | null; usedMemory: boolean }> =>
    ipcRenderer.invoke("chat:send", message),
  notifySpeakingStart: (): void => ipcRenderer.send("audio:speaking-start"),
  notifySpeakingEnd: (): void => ipcRenderer.send("audio:speaking-end"),
  getHistory: (): Promise<ConversationTurn[]> => ipcRenderer.invoke("chat:get-history"),
  onNewExchange: (callback: (payload: NewExchangePayload) => void): void => {
    ipcRenderer.on("chat:new-exchange", (_event, payload: NewExchangePayload) => callback(payload));
  },
});
