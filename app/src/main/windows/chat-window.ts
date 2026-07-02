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
    width: 820,
    height: 880,
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

export function showChatWindow(): void {
  if (!chatWindow) return;
  chatWindow.show();
  chatWindow.focus();
}

export function getChatWindow(): BrowserWindow | null {
  return chatWindow;
}
