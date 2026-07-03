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

export interface Diagnostics {
  ok: boolean;
  ollamaReachable: boolean;
  brainModelPresent: boolean;
  embeddingModelPresent: boolean;
  brainModelTag: string;
  embeddingModelTag: string;
  problems: string[];
}

export async function getDiagnostics(): Promise<Diagnostics> {
  const res = await fetch(`${baseUrl()}/diagnostics`);
  if (!res.ok) {
    throw new Error(`brain /diagnostics ha risposto ${res.status}`);
  }
  const data = (await res.json()) as {
    ok: boolean;
    ollama_reachable: boolean;
    brain_model_present: boolean;
    embedding_model_present: boolean;
    brain_model_tag: string;
    embedding_model_tag: string;
    problems: string[];
  };
  return {
    ok: data.ok,
    ollamaReachable: data.ollama_reachable,
    brainModelPresent: data.brain_model_present,
    embeddingModelPresent: data.embedding_model_present,
    brainModelTag: data.brain_model_tag,
    embeddingModelTag: data.embedding_model_tag,
    problems: data.problems,
  };
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

export interface ConversationTurn {
  id: number;
  eventType: "user_message" | "bot_reply";
  content: string;
  createdAt: string;
}

export async function getConversationHistory(limit = 100): Promise<ConversationTurn[]> {
  const res = await fetch(`${baseUrl()}/conversation/history?limit=${limit}`);
  if (!res.ok) {
    throw new Error(`brain /conversation/history ha risposto ${res.status}`);
  }
  const data = (await res.json()) as {
    turns: { id: number; event_type: "user_message" | "bot_reply"; content: string; created_at: string }[];
  };
  return data.turns.map((t) => ({ id: t.id, eventType: t.event_type, content: t.content, createdAt: t.created_at }));
}

export interface DreamingStatus {
  lastDreamAt: string | null;
  nextScheduledAt: string | null;
}

export async function getDreamingStatus(): Promise<DreamingStatus> {
  const res = await fetch(`${baseUrl()}/dreaming/status`);
  if (!res.ok) {
    throw new Error(`brain /dreaming/status ha risposto ${res.status}`);
  }
  const data = (await res.json()) as { last_dream_at: string | null; next_scheduled_at: string | null };
  return { lastDreamAt: data.last_dream_at, nextScheduledAt: data.next_scheduled_at };
}

export interface QuantumStatus {
  active: boolean;
  iterationsDone: number;
}

function parseQuantumStatus(data: { active: boolean; iterations_done: number }): QuantumStatus {
  return { active: data.active, iterationsDone: data.iterations_done };
}

export async function startQuantumMode(): Promise<QuantumStatus> {
  const res = await fetch(`${baseUrl()}/quantum/start`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`brain /quantum/start ha risposto ${res.status}`);
  }
  return parseQuantumStatus((await res.json()) as { active: boolean; iterations_done: number });
}

export async function stopQuantumMode(): Promise<QuantumStatus> {
  const res = await fetch(`${baseUrl()}/quantum/stop`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`brain /quantum/stop ha risposto ${res.status}`);
  }
  return parseQuantumStatus((await res.json()) as { active: boolean; iterations_done: number });
}

export async function getQuantumStatus(): Promise<QuantumStatus> {
  const res = await fetch(`${baseUrl()}/quantum/status`);
  if (!res.ok) {
    throw new Error(`brain /quantum/status ha risposto ${res.status}`);
  }
  return parseQuantumStatus((await res.json()) as { active: boolean; iterations_done: number });
}
