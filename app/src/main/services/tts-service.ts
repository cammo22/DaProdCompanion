/**
 * Wiring specifico del servizio "tts", sullo stesso modello di brain-service.ts.
 */

import path from "node:path";
import { getConfig, pythonExecutablePath, REPO_ROOT, resolvedSandboxRoot } from "../config";
import { createServiceLogger } from "../logging";
import { ProcessSupervisor } from "./process-supervisor";

export function createTtsSupervisor(): ProcessSupervisor {
  const config = getConfig();
  const sandboxRoot = resolvedSandboxRoot(config.botName || "Companion");
  const logger = createServiceLogger(path.join(sandboxRoot, "logs"), "tts");

  return new ProcessSupervisor({
    name: "tts",
    pythonExecutable: pythonExecutablePath(),
    args: ["-m", "tts_service"],
    cwd: REPO_ROOT,
    healthUrl: `http://127.0.0.1:${config.ttsHttpPort}/health`,
    shutdownUrl: `http://127.0.0.1:${config.ttsHttpPort}/shutdown`,
    env: { ...process.env },
    logger,
    // Il primo avvio in assoluto scarica i pesi di Kokoro da Hugging Face:
    // 15s (default) puo' non bastare. Le volte successive sono cache, ~2s.
    healthTimeoutMs: 90000,
  });
}
