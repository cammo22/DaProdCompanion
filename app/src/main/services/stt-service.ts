/**
 * Wiring specifico del servizio "stt", sullo stesso modello di
 * brain-service.ts/tts-service.ts.
 */

import path from "node:path";
import { getConfig, pythonExecutablePath, REPO_ROOT, resolvedSandboxRoot } from "../config";
import { createServiceLogger } from "../logging";
import { ProcessSupervisor } from "./process-supervisor";

export function createSttSupervisor(): ProcessSupervisor {
  const config = getConfig();
  const sandboxRoot = resolvedSandboxRoot(config.botName || "Companion");
  const logger = createServiceLogger(path.join(sandboxRoot, "logs"), "stt");

  return new ProcessSupervisor({
    name: "stt",
    pythonExecutable: pythonExecutablePath(),
    args: ["-m", "stt_service"],
    cwd: REPO_ROOT,
    healthUrl: `http://127.0.0.1:${config.sttHttpPort}/health`,
    shutdownUrl: `http://127.0.0.1:${config.sttHttpPort}/shutdown`,
    env: { ...process.env },
    logger,
    // Il primo avvio scarica il modello Whisper da Hugging Face, come Kokoro per tts.
    healthTimeoutMs: 90000,
  });
}
