/**
 * Client REST verso stt_service: elenco microfoni disponibili (per il menu
 * Impostazioni) e mute/unmute (proxato dall'avatar).
 */

import { getConfig } from "../config";

function baseUrl(): string {
  return `http://127.0.0.1:${getConfig().sttHttpPort}`;
}

export interface MicDevice {
  index: number;
  name: string;
}

export async function listMicDevices(): Promise<MicDevice[]> {
  const res = await fetch(`${baseUrl()}/devices`);
  if (!res.ok) {
    throw new Error(`stt /devices ha risposto ${res.status}`);
  }
  const data = (await res.json()) as { devices: MicDevice[] };
  return data.devices;
}

export async function toggleMicMute(): Promise<boolean> {
  const res = await fetch(`${baseUrl()}/mic/toggle-mute`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`stt /mic/toggle-mute ha risposto ${res.status}`);
  }
  const data = (await res.json()) as { muted: boolean };
  return data.muted;
}

export async function getMicMuteState(): Promise<boolean> {
  const res = await fetch(`${baseUrl()}/mic/mute-state`);
  if (!res.ok) {
    throw new Error(`stt /mic/mute-state ha risposto ${res.status}`);
  }
  const data = (await res.json()) as { muted: boolean };
  return data.muted;
}
