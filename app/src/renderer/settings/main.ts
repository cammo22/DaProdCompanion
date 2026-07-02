/**
 * Script della finestra impostazioni, caricato come modulo ES per restare
 * isolato dagli altri script renderer (vedi nota in avatar/main.ts).
 */
export {};

interface SettingsPayload {
  botName: string;
  brainModelTag: string;
  ttsVoiceId: string;
  ttsSpeed: number;
  micDeviceIndex: number | null;
}

interface MicDevice {
  index: number;
  name: string;
}

interface OllamaModel {
  name: string;
}

declare const settingsAPI: {
  get(): Promise<SettingsPayload>;
  save(payload: SettingsPayload): Promise<void>;
  restartApp(): Promise<void>;
  resetMemory(): Promise<{ status: string }>;
  listMicDevices(): Promise<MicDevice[]>;
  listOllamaModels(): Promise<OllamaModel[]>;
};

const RESET_CONFIRM_WORD = "RESET";

async function loadMicDevices(currentIndex: number | null): Promise<void> {
  const select = document.getElementById("mic-device") as HTMLSelectElement;
  const devices = await settingsAPI.listMicDevices();

  for (const device of devices) {
    const option = document.createElement("option");
    option.value = String(device.index);
    option.textContent = device.name;
    select.appendChild(option);
  }

  select.value = currentIndex !== null ? String(currentIndex) : "";
}

async function loadModelOptions(currentTag: string): Promise<void> {
  const select = document.getElementById("model-tag") as HTMLSelectElement;
  const hint = document.getElementById("model-tag-hint") as HTMLElement;
  select.innerHTML = "";

  const models = await settingsAPI.listOllamaModels();
  hint.classList.toggle("hidden", models.length > 0);

  // Il tag salvato in .env potrebbe non essere (piu') tra i modelli scaricati
  // localmente (es. rinominato o rimosso con 'ollama rm'): lo si aggiunge
  // comunque come opzione, cosi' il menu non mostra mai un valore vuoto o
  // silenziosamente diverso da quello davvero configurato.
  const names = new Set(models.map((model) => model.name));
  if (currentTag && !names.has(currentTag)) {
    names.add(currentTag);
  }

  for (const name of names) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    select.appendChild(option);
  }

  if (names.size === 0) {
    const option = document.createElement("option");
    option.value = currentTag;
    option.textContent = currentTag || "Nessun modello trovato";
    select.appendChild(option);
  }

  select.value = currentTag;
}

async function loadCurrentSettings(): Promise<void> {
  const current = await settingsAPI.get();
  (document.getElementById("bot-name") as HTMLInputElement).value = current.botName;
  (document.getElementById("tts-voice") as HTMLSelectElement).value = current.ttsVoiceId;
  (document.getElementById("tts-speed") as HTMLInputElement).value = String(current.ttsSpeed);
  await loadModelOptions(current.brainModelTag);
  await loadMicDevices(current.micDeviceIndex);
}

function initSaveForm(): void {
  const form = document.getElementById("settings-form") as HTMLFormElement;
  const saveMessage = document.getElementById("save-message") as HTMLElement;
  const restartButton = document.getElementById("restart-button") as HTMLButtonElement;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const micDeviceValue = (document.getElementById("mic-device") as HTMLSelectElement).value;
    const payload: SettingsPayload = {
      botName: (document.getElementById("bot-name") as HTMLInputElement).value.trim(),
      brainModelTag: (document.getElementById("model-tag") as HTMLSelectElement).value.trim(),
      ttsVoiceId: (document.getElementById("tts-voice") as HTMLSelectElement).value,
      ttsSpeed: Number((document.getElementById("tts-speed") as HTMLInputElement).value),
      micDeviceIndex: micDeviceValue === "" ? null : Number(micDeviceValue),
    };
    await settingsAPI.save(payload);
    saveMessage.classList.remove("hidden");
  });

  restartButton.addEventListener("click", () => {
    settingsAPI.restartApp();
  });
}

function initResetSection(): void {
  const confirmInput = document.getElementById("reset-confirm") as HTMLInputElement;
  const resetButton = document.getElementById("reset-button") as HTMLButtonElement;
  const resetMessage = document.getElementById("reset-message") as HTMLElement;

  confirmInput.addEventListener("input", () => {
    resetButton.disabled = confirmInput.value.trim() !== RESET_CONFIRM_WORD;
  });

  resetButton.addEventListener("click", async () => {
    resetButton.disabled = true;
    resetMessage.textContent = "Reset in corso...";
    resetMessage.classList.remove("hidden");
    try {
      await settingsAPI.resetMemory();
      resetMessage.textContent = "Fatto. Tutta la memoria e' stata cancellata.";
      confirmInput.value = "";
    } catch (err) {
      resetMessage.textContent = "Reset fallito, riprova.";
      resetButton.disabled = false;
    }
  });
}

function init(): void {
  loadCurrentSettings();
  initSaveForm();
  initResetSection();
}

init();
