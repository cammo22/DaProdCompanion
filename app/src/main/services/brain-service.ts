/**
 * Wiring specifico del servizio "brain": configura il ProcessSupervisor
 * generico con i parametri concreti (eseguibile Python, porta, cartella dei
 * log sotto la sandbox del bot).
 */

import path from "node:path";
import { getConfig, pythonExecutablePath, REPO_ROOT, resolvedSandboxRoot } from "../config";
import { createServiceLogger } from "../logging";
import { ProcessSupervisor } from "./process-supervisor";

export function createBrainSupervisor(): ProcessSupervisor {
  const config = getConfig();
  const sandboxRoot = resolvedSandboxRoot(config.botName || "Companion");
  const logger = createServiceLogger(path.join(sandboxRoot, "logs"), "brain");

  return new ProcessSupervisor({
    name: "brain",
    pythonExecutable: pythonExecutablePath(),
    args: ["-m", "brain_service"],
    cwd: REPO_ROOT,
    healthUrl: `http://127.0.0.1:${config.brainHttpPort}/health`,
    shutdownUrl: `http://127.0.0.1:${config.brainHttpPort}/shutdown`,
    env: { ...process.env },
    logger,
  });
}
