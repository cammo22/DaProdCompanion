// Il timer di auto-nascondimento della bubble vive qui (non nel main
// process) apposta: deve mettersi in pausa quando il mouse ci passa sopra,
// e ripartire da capo quando il mouse esce, come richiesto dall'utente.
let hideTimer = null;
let currentBubbleDurationMs = 8000;
let isDreamingBubble = false;
function setState(state) {
    const avatarEl = document.getElementById("avatar");
    if (avatarEl)
        avatarEl.dataset.state = state;
}
function clearHideTimer() {
    if (hideTimer) {
        clearTimeout(hideTimer);
        hideTimer = null;
    }
}
function hideBubble() {
    clearHideTimer();
    document.getElementById("bubble")?.classList.add("hidden");
}
function scheduleHide(durationMs) {
    clearHideTimer();
    hideTimer = setTimeout(hideBubble, durationMs);
}
function setSkipButtonEnabled(enabled) {
    const button = document.getElementById("skip-button");
    if (button)
        button.disabled = !enabled;
}
function playVoiceAudio(url) {
    const audioEl = document.getElementById("voice-audio");
    if (!audioEl)
        return;
    audioEl.src = url;
    // Stesso motivo di chat/main.ts: muta il microfono per la durata reale
    // della riproduzione, non solo per la chat testuale.
    avatarAPI.notifySpeakingStart();
    setSkipButtonEnabled(true);
    const onPlaybackDone = () => {
        avatarAPI.notifySpeakingEnd();
        setSkipButtonEnabled(false);
    };
    audioEl.addEventListener("ended", onPlaybackDone, { once: true });
    audioEl.addEventListener("error", onPlaybackDone, { once: true });
    audioEl.play().catch((err) => {
        console.error("Riproduzione audio vocale fallita:", err);
        onPlaybackDone();
    });
}
function skipVoiceAudio() {
    const audioEl = document.getElementById("voice-audio");
    if (!audioEl || audioEl.paused)
        return;
    audioEl.pause();
    // pause() non genera 'ended': lo stesso cleanup va innescato qui a mano.
    avatarAPI.notifySpeakingEnd();
    setSkipButtonEnabled(false);
}
function initSkipButton() {
    const button = document.getElementById("skip-button");
    if (!button)
        return;
    button.addEventListener("click", (event) => {
        event.stopPropagation();
        skipVoiceAudio();
    });
}
function showReplyBubble(payload) {
    isDreamingBubble = false;
    currentBubbleDurationMs = payload.suggestedDurationMs;
    hidePartialTranscript(); // la risposta vera e' arrivata, l'anteprima non serve piu'
    hideHistoryPanel(); // stessa area della bolla: senza chiuderlo, la nuova risposta resterebbe nascosta dietro
    const bubbleEl = document.getElementById("bubble");
    const textEl = document.getElementById("bubble-text");
    const badgeEl = document.getElementById("bubble-badge");
    const userMessageEl = document.getElementById("bubble-user-message");
    if (!bubbleEl || !textEl || !badgeEl || !userMessageEl)
        return;
    // Si vede sempre sia cosa e' stato detto sia la risposta, non solo la
    // risposta da sola: l'utente ha chiesto esplicitamente di vedere entrambi
    // i lati dello scambio nella bolla dell'avatar.
    if (payload.userMessage) {
        userMessageEl.textContent = `Tu: ${payload.userMessage}`;
        userMessageEl.classList.remove("hidden");
    }
    else {
        userMessageEl.classList.add("hidden");
    }
    textEl.textContent = payload.text;
    badgeEl.classList.toggle("hidden", !payload.usedMemory);
    bubbleEl.classList.remove("hidden");
    // Presente solo per le risposte innescate dalla voce (chat testuale la
    // riproduce gia' nella propria finestra, vedi flashReply in avatar-window.ts).
    if (payload.audioUrl)
        playVoiceAudio(payload.audioUrl);
    scheduleHide(currentBubbleDurationMs);
}
function showPartialTranscript(text) {
    const el = document.getElementById("partial-transcript");
    if (!el)
        return;
    if (!text) {
        hidePartialTranscript();
        return;
    }
    hideHistoryPanel(); // stessa area della bolla, vedi showReplyBubble
    el.textContent = `Tu: ${text}...`;
    el.classList.remove("hidden");
}
function hidePartialTranscript() {
    document.getElementById("partial-transcript")?.classList.add("hidden");
}
function hideHistoryPanel() {
    document.getElementById("history-panel")?.classList.add("hidden");
}
function showDreamingBubble() {
    isDreamingBubble = true;
    clearHideTimer(); // niente auto-hide: segue lo stato reale del dreaming
    hideHistoryPanel(); // stessa area della bolla, vedi showReplyBubble
    const bubbleEl = document.getElementById("bubble");
    const textEl = document.getElementById("bubble-text");
    const badgeEl = document.getElementById("bubble-badge");
    const userMessageEl = document.getElementById("bubble-user-message");
    if (!bubbleEl || !textEl || !badgeEl)
        return;
    textEl.textContent = "Sognando...";
    badgeEl.classList.add("hidden");
    userMessageEl?.classList.add("hidden");
    bubbleEl.classList.remove("hidden");
}
function setMicMuteIcon(muted) {
    const button = document.getElementById("mic-mute-button");
    const icon = document.getElementById("mic-mute-icon");
    if (!button || !icon)
        return;
    icon.textContent = muted ? "🔇" : "🎤";
    button.classList.toggle("muted", muted);
    button.title = muted ? "Microfono mutato: clicca per riattivare" : "Microfono attivo: clicca per mutare";
}
function initMicMuteButton() {
    const button = document.getElementById("mic-mute-button");
    if (!button)
        return;
    avatarAPI.getMicMuteState().then(setMicMuteIcon);
    button.addEventListener("click", (event) => {
        event.stopPropagation(); // non deve anche aprire la chat (click sull'avatar sotto)
        avatarAPI.toggleMicMute().then(setMicMuteIcon);
    });
}
// Stato locale dei due pulsanti (registra/live): stt_service e' la fonte di
// verita' (vedi RecordingState/ConversationWindow), ma qui basta rispecchiare
// cio' che l'utente ha appena cliccato per aggiornare subito l'icona, senza
// aspettare un giro di polling.
let isRecording = false;
let isLive = false;
function initRecordButton() {
    const button = document.getElementById("record-button");
    const icon = document.getElementById("record-icon");
    if (!button || !icon)
        return;
    button.addEventListener("click", (event) => {
        event.stopPropagation(); // non deve anche aprire la chat
        if (isRecording) {
            isRecording = false;
            button.classList.remove("recording");
            icon.textContent = "🎙️";
            button.title = "Clicca per registrare, clicca di nuovo per inviare";
            avatarAPI.stopRecording().catch((err) => {
                console.error("Impossibile fermare la registrazione:", err);
            });
        }
        else {
            isRecording = true;
            button.classList.add("recording");
            icon.textContent = "⏺️";
            button.title = "Clicca di nuovo per inviare";
            avatarAPI.startRecording().catch((err) => {
                console.error("Impossibile avviare la registrazione:", err);
            });
        }
    });
}
function initLiveButton() {
    const button = document.getElementById("live-button");
    if (!button)
        return;
    button.addEventListener("click", (event) => {
        event.stopPropagation();
        if (isLive) {
            isLive = false;
            button.classList.remove("active");
            button.title = "Modalita' live: parla senza dire il nome del bot";
            avatarAPI.stopLiveMode().catch((err) => {
                console.error("Impossibile fermare la modalita' live:", err);
            });
        }
        else {
            isLive = true;
            button.classList.add("active");
            button.title = "Modalita' live attiva: clicca per fermarla";
            avatarAPI.startLiveMode().catch((err) => {
                console.error("Impossibile avviare la modalita' live:", err);
            });
        }
    });
}
function formatHistoryTime(iso) {
    return new Date(iso).toLocaleString("it-IT", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}
async function loadHistoryPanel() {
    const listEl = document.getElementById("history-list");
    if (!listEl)
        return;
    listEl.textContent = "Caricamento...";
    try {
        const turns = await avatarAPI.getHistory();
        listEl.innerHTML = "";
        if (turns.length === 0) {
            listEl.textContent = "Nessun messaggio ancora.";
            return;
        }
        for (const turn of turns) {
            const entry = document.createElement("div");
            entry.className = `history-entry history-entry-${turn.eventType === "user_message" ? "user" : "bot"}`;
            const label = turn.eventType === "user_message" ? "Tu" : "Babbasone";
            entry.textContent = `${label} (${formatHistoryTime(turn.createdAt)}): ${turn.content}`;
            listEl.appendChild(entry);
        }
        listEl.scrollTop = listEl.scrollHeight;
    }
    catch (err) {
        listEl.textContent = "Impossibile caricare la cronologia.";
        console.error("Caricamento cronologia avatar fallito:", err);
    }
}
function initHistoryToggle() {
    const button = document.getElementById("history-toggle-button");
    const panel = document.getElementById("history-panel");
    const closeButton = document.getElementById("history-close-button");
    if (!button || !panel || !closeButton)
        return;
    button.addEventListener("click", (event) => {
        event.stopPropagation();
        const willShow = panel.classList.contains("hidden");
        panel.classList.toggle("hidden", !willShow);
        if (willShow)
            loadHistoryPanel();
    });
    closeButton.addEventListener("click", (event) => {
        event.stopPropagation();
        panel.classList.add("hidden");
    });
}
function init() {
    avatarAPI.onStateChange((state) => setState(state));
    avatarAPI.onBubble((payload) => showReplyBubble(payload));
    avatarAPI.onDreamingStart(() => showDreamingBubble());
    avatarAPI.onDreamingEnd(() => hideBubble());
    avatarAPI.onPartialTranscript((text) => showPartialTranscript(text));
    document.getElementById("avatar")?.addEventListener("click", () => {
        avatarAPI.openChat();
    });
    initMicMuteButton();
    initRecordButton();
    initLiveButton();
    initSkipButton();
    initHistoryToggle();
    const bubbleEl = document.getElementById("bubble");
    bubbleEl?.addEventListener("mouseenter", () => {
        if (isDreamingBubble)
            return; // la bubble "sognando" non ha un timer da mettere in pausa
        clearHideTimer();
    });
    bubbleEl?.addEventListener("mouseleave", () => {
        if (isDreamingBubble)
            return;
        scheduleHide(currentBubbleDurationMs);
    });
}
init();
export {};
