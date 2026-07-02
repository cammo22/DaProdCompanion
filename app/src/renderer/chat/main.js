let currentAudio = null;
function appendMessage(text, sender) {
    const container = document.getElementById("messages");
    if (!container)
        return;
    const el = document.createElement("div");
    el.className = `message message-${sender}`;
    el.textContent = text;
    container.appendChild(el);
    container.scrollTop = container.scrollHeight;
}
function setSkipButtonEnabled(enabled) {
    const button = document.getElementById("skip-button");
    if (button)
        button.disabled = !enabled;
}
function playAudio(url) {
    const audio = new Audio(url);
    currentAudio = audio;
    // Muta il microfono per la durata reale di questa riproduzione (non una
    // stima): senza, il microfono sempre acceso rischia di captare la voce
    // del companion dalle casse e scambiarla per un nuovo comando.
    chatAPI.notifySpeakingStart();
    setSkipButtonEnabled(true);
    const onPlaybackDone = () => {
        chatAPI.notifySpeakingEnd();
        setSkipButtonEnabled(false);
        if (currentAudio === audio)
            currentAudio = null;
    };
    audio.addEventListener("ended", onPlaybackDone, { once: true });
    audio.addEventListener("error", onPlaybackDone, { once: true });
    audio.play().catch((err) => {
        console.error("Riproduzione audio fallita:", err);
        onPlaybackDone();
    });
}
function skipAudio() {
    if (!currentAudio)
        return;
    currentAudio.pause();
    // pause() non genera l'evento 'ended': lo stesso cleanup (smuta il
    // microfono, disabilita il pulsante) va innescato qui a mano.
    chatAPI.notifySpeakingEnd();
    setSkipButtonEnabled(false);
    currentAudio = null;
}
function init() {
    const form = document.getElementById("chat-form");
    const input = document.getElementById("chat-input");
    const skipButton = document.getElementById("skip-button");
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const message = input.value.trim();
        if (!message)
            return;
        appendMessage(message, "user");
        input.value = "";
        input.disabled = true;
        try {
            const { reply, audioUrl } = await chatAPI.sendMessage(message);
            appendMessage(reply, "bot");
            if (audioUrl)
                playAudio(audioUrl);
        }
        catch (err) {
            appendMessage("Errore nel contattare il companion. Riprova.", "bot");
        }
        finally {
            input.disabled = false;
            input.focus();
        }
    });
    skipButton.addEventListener("click", () => skipAudio());
    input.focus();
}
init();
export {};
