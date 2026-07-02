/**
 * Handler IPC della chat: inoltra il messaggio a brain_service, converte il
 * percorso audio locale in una file:// URL riproducibile dal renderer, e
 * coordina lo stato dell'avatar (thinking mentre si aspetta la risposta,
 * speaking con la bubble per la durata reale dell'audio quando disponibile).
 */

import { ipcMain } from "electron";
import { pathToFileURL } from "node:url";
import { sendChatMessage } from "../clients/brain-client";
import { flashReply, setAvatarState } from "../windows/avatar-window";

export interface ChatIpcResult {
  reply: string;
  audioUrl: string | null;
}

export function registerChatHandlers(): void {
  ipcMain.handle("chat:send", async (_event, message: string): Promise<ChatIpcResult> => {
    if (typeof message !== "string" || !message.trim()) {
      throw new Error("Messaggio vuoto");
    }

    setAvatarState("thinking");
    try {
      const { reply, audioPath, durationSeconds, usedMemory } = await sendChatMessage(message);
      const bubbleDurationMs = durationSeconds ? durationSeconds * 1000 + 500 : undefined;
      flashReply(reply, usedMemory, bubbleDurationMs);

      const audioUrl = audioPath ? pathToFileURL(audioPath).href : null;
      return { reply, audioUrl };
    } catch (err) {
      setAvatarState("idle");
      throw err;
    }
  });
}
