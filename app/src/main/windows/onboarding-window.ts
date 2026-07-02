/**
 * Finestra di onboarding: chiede il nome del companion (default "Babbasone",
 * sempre modificabile) prima di avviare brain_service, cosi' il first-run
 * setup Python (che altrimenti chiederebbe input() da terminale) trova gia'
 * BOT_NAME impostato quando viene lanciato come figlio di Electron.
 *
 * Riusata anche per la rinomina successiva (vedi ipc/settings-handlers.ts):
 * la promise si risolve sempre con il nome scelto, sia al primo avvio sia in
 * un secondo momento.
 */

import { BrowserWindow, ipcMain } from "electron";
import path from "node:path";

export function showOnboardingWindow(defaultName: string): Promise<string> {
  return new Promise((resolve) => {
    const win = new BrowserWindow({
      width: 440,
      height: 280,
      resizable: false,
      title: "Benvenuto",
      webPreferences: {
        preload: path.join(__dirname, "../../preload/onboarding-preload.js"),
        contextIsolation: true,
        nodeIntegration: false,
      },
    });
    win.setMenuBarVisibility(false);
    win.loadFile(path.join(__dirname, "../../../src/renderer/onboarding/index.html"));

    let settled = false;

    ipcMain.handleOnce("onboarding:get-default-name", () => defaultName);
    ipcMain.handleOnce("onboarding:submit-name", (_event, name: string) => {
      settled = true;
      win.close();
      resolve(name);
    });

    win.on("closed", () => {
      // Se l'utente chiude la finestra senza confermare, non blocchiamo
      // l'avvio all'infinito: si procede con il nome di default proposto.
      // (resolve() dopo che submit-name ha gia' risolto e' un no-op innocuo:
      // una Promise puo' essere risolta una sola volta.)
      if (!settled) resolve(defaultName);
    });
  });
}
