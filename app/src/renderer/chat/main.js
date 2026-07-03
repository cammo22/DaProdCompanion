let currentAudio = null;
function formatMessageTime(date) {
    return date.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" });
}
function appendMessage(text, sender, options = {}) {
    const container = document.getElementById("messages");
    if (!container)
        return;
    const el = document.createElement("div");
    el.className = `message message-${sender}`;
    const textEl = document.createElement("div");
    textEl.className = "message-text";
    textEl.textContent = text;
    el.appendChild(textEl);
    const meta = document.createElement("div");
    meta.className = "message-meta";
    meta.textContent = formatMessageTime(options.time ?? new Date());
    if (options.usedMemory) {
        const badge = document.createElement("span");
        badge.className = "message-memory-badge";
        badge.title = "Ha usato la memoria";
        badge.textContent = "🧠";
        meta.appendChild(badge);
    }
    el.appendChild(meta);
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
async function loadHistory() {
    try {
        const turns = await chatAPI.getHistory();
        for (const turn of turns) {
            appendMessage(turn.content, turn.eventType === "user_message" ? "user" : "bot", {
                time: new Date(turn.createdAt),
            });
        }
    }
    catch (err) {
        // Puo' succedere al primissimo caricamento in background, prima che
        // brain_service sia pronto: non e' un errore fatale, la finestra resta
        // semplicemente vuota finche' non arriva il primo scambio reale.
        console.warn("Impossibile caricare la cronologia (probabilmente brain_service non e' ancora pronto):", err);
    }
}
function init() {
    const form = document.getElementById("chat-form");
    const input = document.getElementById("chat-input");
    const skipButton = document.getElementById("skip-button");
    loadHistory();
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const message = input.value.trim();
        if (!message)
            return;
        appendMessage(message, "user");
        input.value = "";
        input.disabled = true;
        try {
            const { reply, audioUrl, usedMemory } = await chatAPI.sendMessage(message);
            appendMessage(reply, "bot", { usedMemory });
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
    // Scambi innescati dalla voce: l'audio lo riproduce gia' l'avatar (vedi
    // handleBrainEvent in index.ts), qui si mostra solo il testo.
    chatAPI.onNewExchange(({ userMessage, reply, usedMemory }) => {
        appendMessage(userMessage, "user");
        appendMessage(reply, "bot", { usedMemory });
    });
    input.focus();
}
init();
export {};
