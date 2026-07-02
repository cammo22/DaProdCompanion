/**
 * Client WebSocket persistente verso il canale eventi di brain_service
 * (/ws). Si riconnette automaticamente se la connessione cade (es. durante
 * un riavvio di brain_service gestito dal supervisor). Ogni messaggio e' un
 * JSON con un campo 'type' discriminante (vedi brain_service/events/bus.py).
 *
 * Usa il pacchetto 'ws': il processo main di Electron non ha un WebSocket
 * globale nonostante Node 26 lo abbia sul sistema (Electron include una
 * build Node propria, verificato empiricamente — "WebSocket is not defined"
 * al primo avvio).
 */

import WebSocket from "ws";

export interface BrainEvent {
  type: string;
  [key: string]: unknown;
}

export type BrainEventHandler = (event: BrainEvent) => void;

export class BrainEventClient {
  private socket: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private closedIntentionally = false;

  constructor(
    private readonly url: string,
    private readonly onEvent: BrainEventHandler,
  ) {}

  connect(): void {
    this.closedIntentionally = false;
    const socket = new WebSocket(this.url);
    this.socket = socket;

    socket.on("message", (data) => {
      try {
        const parsed = JSON.parse(data.toString()) as BrainEvent;
        this.onEvent(parsed);
      } catch {
        // messaggio non JSON valido: ignorato
      }
    });

    socket.on("close", () => {
      if (this.closedIntentionally) return;
      this.reconnectTimer = setTimeout(() => this.connect(), 2000);
    });

    socket.on("error", () => {
      socket.close();
    });
  }

  close(): void {
    this.closedIntentionally = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.socket?.close();
  }
}
