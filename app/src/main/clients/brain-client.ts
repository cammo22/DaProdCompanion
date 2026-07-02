/**
 * Client REST verso brain_service. /chat ora restituisce anche il riferimento
 * audio (generato da tts_service tramite brain), oltre al testo.
 */

import { getConfig } from "../config";

function baseUrl(): string {
  return `http://127.0.0.1:${getConfig().brainHttpPort}`;
}

export interface ChatResult {
  reply: string;
  audioPath: string | null;
  durationSeconds: number | null;
  usedMemory: boolean;
}

export async function sendChatMessage(message: string): Promise<ChatResult> {
  const res = await fetch(`${baseUrl()}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) {
    throw new Error(`brain /chat ha risposto ${res.status}`);
  }
  const data = (await res.json()) as {
    reply: string;
    audio_path: string | null;
    duration_seconds: number | null;
    used_memory: boolean;
  };
  return {
    reply: data.reply,
    audioPath: data.audio_path,
    durationSeconds: data.duration_seconds,
    usedMemory: data.used_memory,
  };
}

export async function getBrainHealth(): Promise<{ status: string; bot_name: string }> {
  const res = await fetch(`${baseUrl()}/health`);
  if (!res.ok) {
    throw new Error(`brain /health ha risposto ${res.status}`);
  }
  return (await res.json()) as { status: string; bot_name: string };
}

export interface GraphSnapshot {
  nodes: { id: number; node_type: string; label: string }[];
  edges: { id: number; source_node_id: number; target_node_id: number; edge_type: string }[];
}

export async function getGraphSnapshot(): Promise<GraphSnapshot> {
  const res = await fetch(`${baseUrl()}/graph/snapshot`);
  if (!res.ok) {
    throw new Error(`brain /graph/snapshot ha risposto ${res.status}`);
  }
  return (await res.json()) as GraphSnapshot;
}

export async function triggerDreaming(): Promise<{ consolidated_events: number }> {
  const res = await fetch(`${baseUrl()}/dreaming/run`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`brain /dreaming/run ha risposto ${res.status}`);
  }
  return (await res.json()) as { consolidated_events: number };
}

export async function resetAllMemory(): Promise<{ status: string }> {
  const res = await fetch(`${baseUrl()}/admin/reset`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`brain /admin/reset ha risposto ${res.status}`);
  }
  return (await res.json()) as { status: string };
}
