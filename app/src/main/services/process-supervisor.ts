/**
 * Supervisore generico di un processo Python figlio: spawn, attesa di
 * readiness via polling di /health, riavvio con backoff in caso di crash
 * inatteso, spegnimento pulito (POST /shutdown, poi kill come fallback).
 * Stesso codice per brain/webcam/tts: cambia solo la ServiceConfig passata.
 */

import { spawn, type ChildProcess } from "node:child_process";
import type { ServiceLogger } from "../logging";

export interface ServiceConfig {
  name: string;
  pythonExecutable: string;
  args: string[];
  cwd: string;
  healthUrl: string;
  shutdownUrl: string;
  env: NodeJS.ProcessEnv;
  logger: ServiceLogger;
  /** Timeout readiness in ms (default 15000). Piu' alto per servizi che
   * possono scaricare pesi/modelli al primo avvio (es. tts, la prima volta
   * che Kokoro scarica i pesi da Hugging Face). */
  healthTimeoutMs?: number;
}

export class ProcessSupervisor {
  private child: ChildProcess | null = null;
  private restartAttempts = 0;
  private readonly maxRestartAttempts = 5;
  private stoppedIntentionally = false;

  constructor(private readonly config: ServiceConfig) {}

  async start(): Promise<void> {
    this.stoppedIntentionally = false;
    this.spawnProcess();
    await this.waitForHealth(this.config.healthTimeoutMs ?? 15000);
    this.restartAttempts = 0;
  }

  private spawnProcess(): void {
    this.child = spawn(this.config.pythonExecutable, this.config.args, {
      cwd: this.config.cwd,
      env: this.config.env,
      windowsHide: true,
    });

    this.child.stdout?.on("data", (chunk) => this.config.logger.write(chunk, false));
    this.child.stderr?.on("data", (chunk) => this.config.logger.write(chunk, true));

    this.child.on("exit", (code) => {
      if (this.stoppedIntentionally) return;

      this.config.logger.write(`processo terminato inaspettatamente (code=${code})\n`, true);

      if (this.restartAttempts >= this.maxRestartAttempts) {
        this.config.logger.write("troppi riavvii falliti, mi fermo\n", true);
        return;
      }
      this.restartAttempts += 1;
      const delayMs = Math.min(1000 * 2 ** this.restartAttempts, 30000);
      setTimeout(() => this.spawnProcess(), delayMs);
    });
  }

  private async waitForHealth(timeoutMs: number): Promise<void> {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      try {
        const res = await fetch(this.config.healthUrl);
        if (res.ok) return;
      } catch {
        // non ancora pronto, si ritenta
      }
      await new Promise((resolve) => setTimeout(resolve, 300));
    }
    throw new Error(`${this.config.name} non risponde a ${this.config.healthUrl} dopo ${timeoutMs}ms`);
  }

  async stop(): Promise<void> {
    this.stoppedIntentionally = true;
    if (!this.child) return;

    try {
      await fetch(this.config.shutdownUrl, { method: "POST" });
    } catch {
      // il servizio potrebbe essere gia' morto o non ancora pronto: si passa al kill
    }
    await this.waitForExit(3000);
    if (this.child && this.child.exitCode === null) {
      this.child.kill();
    }
    this.config.logger.close();
  }

  private async waitForExit(timeoutMs: number): Promise<void> {
    const child = this.child;
    if (!child || child.exitCode !== null) return;
    await new Promise<void>((resolve) => {
      const timer = setTimeout(resolve, timeoutMs);
      child.once("exit", () => {
        clearTimeout(timer);
        resolve();
      });
    });
  }
}
