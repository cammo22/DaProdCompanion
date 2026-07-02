/**
 * Finestra impostazioni: nome del bot, modello Ollama, voce e velocita' TTS,
 * piu' il pulsante per resettare tutta la memoria. Le modifiche si scrivono
 * in .env e richiedono un riavvio completo dell'app per applicarsi (piu'
 * semplice e affidabile di un hot-restart selettivo dei singoli servizi
 * Python): la UI offre un pulsante "Riavvia ora" dopo il salvataggio.
 */

import { BrowserWindow } from "electron";
import path from "node:path";
import { isAppQuitting } from "../app-state";

let settingsWindow: BrowserWindow | null = null;

export function createSettingsWindow(): BrowserWindow {
  settingsWindow = new BrowserWindow({
    width: 420,
    height: 620,
    show: false,
    title: "Impostazioni",
    backgroundColor: "#14151f",
    resizable: false,
    webPreferences: {
      preload: path.join(__dirname, "../../preload/settings-preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  settingsWindow.setMenuBarVisibility(false);
  settingsWindow.loadFile(path.join(__dirname, "../../../src/renderer/settings/index.html"));

  settingsWindow.on("close", (event) => {
    if (isAppQuitting()) return;
    event.preventDefault();
    settingsWindow?.hide();
  });

  return settingsWindow;
}

export function showSettingsWindow(): void {
  if (!settingsWindow) return;
  settingsWindow.show();
  settingsWindow.focus();
}
