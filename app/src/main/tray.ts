/**
 * Icona nella system tray di Windows (zona vicino all'orologio): punto di
 * accesso fisso all'app quando resta visibile solo l'avatar sul desktop, dato
 * che l'avatar ha skipTaskbar: true e quindi non compare nella taskbar
 * normale. Click sinistro apre la chat, click destro da' un menu con il
 * toggle dell'avatar e l'uscita pulita (finora l'unico modo per chiudere
 * l'app era il Task Manager: nessuna finestra ha una barra del titolo/menu).
 */

import { app, Menu, Tray } from "electron";
import path from "node:path";
import { getAvatarWindow } from "./windows/avatar-window";
import { showChatWindow } from "./windows/chat-window";
import { showGraphWindow } from "./windows/graph-window";
import { showSettingsWindow } from "./windows/settings-window";

let tray: Tray | null = null;

function iconPath(): string {
  return path.join(__dirname, "../../resources/icons/tray-icon.ico");
}

export function createTray(botName: string): Tray {
  tray = new Tray(iconPath());
  tray.setToolTip(botName);

  const menu = Menu.buildFromTemplate([
    { label: "Apri chat", click: () => showChatWindow() },
    { label: "Apri cervellone", click: () => showGraphWindow() },
    {
      label: "Mostra/nascondi avatar",
      click: () => {
        const avatarWindow = getAvatarWindow();
        if (!avatarWindow) return;
        if (avatarWindow.isVisible()) {
          avatarWindow.hide();
        } else {
          avatarWindow.show();
        }
      },
    },
    { label: "Impostazioni", click: () => showSettingsWindow() },
    { type: "separator" },
    { label: "Esci", click: () => app.quit() },
  ]);
  tray.setContextMenu(menu);

  tray.on("click", () => showChatWindow());

  return tray;
}
