const RESET_CONFIRM_WORD = "RESET";
async function loadMicDevices(currentIndex) {
    const select = document.getElementById("mic-device");
    const devices = await settingsAPI.listMicDevices();
    for (const device of devices) {
        const option = document.createElement("option");
        option.value = String(device.index);
        option.textContent = device.name;
        select.appendChild(option);
    }
    select.value = currentIndex !== null ? String(currentIndex) : "";
}
async function loadCurrentSettings() {
    const current = await settingsAPI.get();
    document.getElementById("bot-name").value = current.botName;
    document.getElementById("model-tag").value = current.brainModelTag;
    document.getElementById("tts-voice").value = current.ttsVoiceId;
    document.getElementById("tts-speed").value = String(current.ttsSpeed);
    await loadMicDevices(current.micDeviceIndex);
}
function initSaveForm() {
    const form = document.getElementById("settings-form");
    const saveMessage = document.getElementById("save-message");
    const restartButton = document.getElementById("restart-button");
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const micDeviceValue = document.getElementById("mic-device").value;
        const payload = {
            botName: document.getElementById("bot-name").value.trim(),
            brainModelTag: document.getElementById("model-tag").value.trim(),
            ttsVoiceId: document.getElementById("tts-voice").value,
            ttsSpeed: Number(document.getElementById("tts-speed").value),
            micDeviceIndex: micDeviceValue === "" ? null : Number(micDeviceValue),
        };
        await settingsAPI.save(payload);
        saveMessage.classList.remove("hidden");
    });
    restartButton.addEventListener("click", () => {
        settingsAPI.restartApp();
    });
}
function initResetSection() {
    const confirmInput = document.getElementById("reset-confirm");
    const resetButton = document.getElementById("reset-button");
    const resetMessage = document.getElementById("reset-message");
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
        }
        catch (err) {
            resetMessage.textContent = "Reset fallito, riprova.";
            resetButton.disabled = false;
        }
    });
}
function init() {
    loadCurrentSettings();
    initSaveForm();
    initResetSection();
}
init();
export {};
