import { ipcMain } from "electron";
import {
  getDreamingStatus,
  getGraphSnapshot,
  triggerDreaming,
  type DreamingStatus,
  type GraphSnapshot,
} from "../clients/brain-client";

const EMPTY_SNAPSHOT: GraphSnapshot = { nodes: [], edges: [] };
const EMPTY_STATUS: DreamingStatus = { lastDreamAt: null, nextScheduledAt: null };

export function registerGraphHandlers(): void {
  ipcMain.handle("graph:get-snapshot", async () => {
    try {
      return await getGraphSnapshot();
    } catch {
      // Puo' succedere al primissimo caricamento in background, prima che
      // brain_service sia pronto: il pannello si riaggiorna comunque ogni
      // volta che viene mostrato (vedi graph-window.ts), non serve propagare
      // l'errore ne' fare rumore nei log per una race di avvio attesa.
      return EMPTY_SNAPSHOT;
    }
  });

  ipcMain.handle("graph:trigger-now", () => triggerDreaming());

  ipcMain.handle("graph:get-dreaming-status", async () => {
    try {
      return await getDreamingStatus();
    } catch {
      return EMPTY_STATUS;
    }
  });
}
