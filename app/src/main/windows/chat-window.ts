/**
 * Finestra di chat testuale: finestra normale (non trasparente/overlay),
 * nascosta di default, mostrata al click sull'avatar. Si nasconde invece di
 * chiudersi alla X (cosi' la cronologia dei messaggi nel renderer non si
 * perde) SOLO quando l'utente chiude la finestra stessa. Se invece l'app sta
 * davvero uscendo (vedi app-state.ts), la chiusura deve procedere per
 * davvero, altrimenti app.quit() non riesce mai a completare: e' il bug
 * segnalato dall'utente ("clic su Esci toglie l'avatar ma non chiude tutto").
 */

import { BrowserWindow } from "electron";
import path from "node:path";
import { isAppQuitting } from "../app-state";

let chatWindow: BrowserWindow | null = null;

export function createChatWindow(): BrowserWindow {
  chatWindow = new BrowserWindow({
    width: 620,
    height: 760,
    show: false,
    title: "Chat",
    webPreferences: {
      preload: path.join(__dirname, "../../preload/chat-preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  chatWindow.setMenuBarVisibility(false);
  chatWindow.loadFile(path.join(__dirname, "../../../src/renderer/chat/index.html"));

  chatWindow.on("close", (event) => {
    if (isAppQuitting()) return;
    event.preventDefault();
    chatWindow?.hide();
  });

  return chatWindow;
}

export function showChatWindow(focus = true): void {
  if (!chatWindow) return;
  chatWindow.show();
  if (focus) chatWindow.focus();
}

export function getChatWindow(): BrowserWindow | null {
  return chatWindow;
}

/** Aggiunge uno scambio (utente + risposta) alla finestra chat gia' aperta,
 * usato per gli scambi innescati dalla voce: la chat testuale li mostra
 * anche se non sono partiti da li', ma non ne riproduce l'audio (gia' fatto
 * dall'avatar, vedi handleBrainEvent in index.ts). */
export function notifyNewExchange(userMessage: string, reply: string): void {
  chatWindow?.webContents.send("chat:new-exchange", { userMessage, reply });
}
