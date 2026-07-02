/**
 * Logger minimale per l'output grezzo (stdout/stderr) dei processi Python
 * figli. E' distinto dal log applicativo strutturato che brain_service scrive
 * gia' da solo (Settings.resolved_log_dir()): questo cattura anche cio' che
 * uvicorn/Python stampano prima che il logging applicativo sia pronto, utile
 * per diagnosticare crash all'avvio.
 */

import fs from "node:fs";
import path from "node:path";

export interface ServiceLogger {
  write(chunk: Buffer | string, isError?: boolean): void;
  close(): void;
}

export function createServiceLogger(logDir: string, serviceName: string): ServiceLogger {
  fs.mkdirSync(logDir, { recursive: true });
  const stream = fs.createWriteStream(path.join(logDir, `${serviceName}-stdio.log`), { flags: "a" });

  return {
    write(chunk: Buffer | string, isError = false): void {
      const text = chunk.toString();
      const prefix = isError ? "[stderr]" : "[stdout]";
      const line = `${new Date().toISOString()} ${prefix} ${text}`;
      stream.write(line.endsWith("\n") ? line : `${line}\n`);
    },
    close(): void {
      stream.end();
    },
  };
}
