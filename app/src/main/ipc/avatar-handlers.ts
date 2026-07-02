import { ipcMain } from "electron";
import {
  getMicMuteState,
  startLiveMode,
  startRecording,
  stopLiveMode,
  stopRecording,
  toggleMicMute,
} from "../clients/stt-client";
import { showChatWindow } from "../windows/chat-window";

export function registerAvatarHandlers(): void {
  ipcMain.on("avatar:open-chat", () => {
    showChatWindow();
  });

  ipcMain.handle("avatar:toggle-mic-mute", async (): Promise<boolean> => {
    return toggleMicMute();
  });

  ipcMain.handle("avatar:get-mic-mute-state", async (): Promise<boolean> => {
    try {
      return await getMicMuteState();
    } catch {
      // stt_service non ancora pronto all'avvio: l'icona parte da "non
      // mutato", si allinea al valore reale al prossimo giro utile.
      return false;
    }
  });

  ipcMain.handle("avatar:start-recording", () => startRecording());
  ipcMain.handle("avatar:stop-recording", () => stopRecording());
  ipcMain.handle("avatar:start-live-mode", () => startLiveMode());
  ipcMain.handle("avatar:stop-live-mode", () => stopLiveMode());
}
