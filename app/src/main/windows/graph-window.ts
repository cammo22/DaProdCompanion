/**
 * Pannello del "cervellone": finestra normale con la vista a grafo
 * (force-graph), nascosta di default, mostrata dal menu della tray. Si
 * comporta come la finestra chat: nasconde invece di chiudere alla X
 * dell'utente, ma lascia procedere la chiusura reale durante lo spegnimento
 * dell'app (vedi app-state.ts).
 */

import { BrowserWindow } from "electron";
import path from "node:path";
import { isAppQuitting } from "../app-state";

let graphWindow: BrowserWindow | null = null;

export function createGraphWindow(): BrowserWindow {
  graphWindow = new BrowserWindow({
    width: 900,
    height: 700,
    show: false,
    title: "Cervellone",
    backgroundColor: "#14151f",
    webPreferences: {
      preload: path.join(__dirname, "../../preload/graph-preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  graphWindow.setMenuBarVisibility(false);
  graphWindow.loadFile(path.join(__dirname, "../../../src/renderer/graph/index.html"));

  graphWindow.on("close", (event) => {
    if (isAppQuitting()) return;
    event.preventDefault();
    graphWindow?.hide();
  });

  return graphWindow;
}

export function showGraphWindow(): void {
  if (!graphWindow) return;
  graphWindow.show();
  graphWindow.focus();
  // Riaggiorna sempre all'apertura: il primissimo caricamento in background
  // (all'avvio dell'app, finestra ancora nascosta) puo' capitare prima che
  // brain_service sia pronto e fallire silenziosamente — riaprire il
  // pannello garantisce comunque dati freschi.
  notifyGraphUpdated();
}

export function notifyGraphUpdated(): void {
  graphWindow?.webContents.send("graph:updated");
}

export function getGraphWindow(): BrowserWindow | null {
  return graphWindow;
}
