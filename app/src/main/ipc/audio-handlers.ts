/**
 * Handler condiviso tra la finestra chat e la finestra avatar (entrambe
 * riproducono audio TTS): mutano il microfono in stt_service esattamente
 * per la durata reale della riproduzione (eventi play/ended del renderer,
 * non una stima della durata), cosi' il microfono sempre acceso non capta
 * la voce del companion dalle casse e rischia di riattivarsi da solo se una
 * risposta contiene il suo nome.
 */

import { ipcMain } from "electron";
import { setSpeakingMute } from "../clients/stt-client";

export function registerAudioHandlers(): void {
  ipcMain.on("audio:speaking-start", () => {
    setSpeakingMute(true).catch((err) => {
      console.error("[audio] impossibile mutare il microfono durante la riproduzione:", err);
    });
  });

  ipcMain.on("audio:speaking-end", () => {
    setSpeakingMute(false).catch((err) => {
      console.error("[audio] impossibile riattivare il microfono dopo la riproduzione:", err);
    });
  });
}
