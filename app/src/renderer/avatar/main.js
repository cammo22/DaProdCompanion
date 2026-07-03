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
    // L'audio si riproduce comunque, anche a vista bloccata.
    if (payload.audioUrl)
        playVoiceAudio(payload.audioUrl);
    // Se la conversazione e' "bloccata" (pin attivo), non mostriamo la bolla
    // volatile: aggiorniamo il visualizzatore fisso e saltiamo all'ultimo
    // scambio, cosi' resta sempre visibile come richiesto.
    if (isPinned) {
        refreshConvo(true);
        return;
    }
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
    scheduleHide(currentBubbleDurationMs);
}
function showPartialTranscript(text) {
    if (isPinned)
        return; // a vista bloccata non copriamo il visualizzatore fisso
    const el = document.getElementById("partial-transcript");
    if (!el)
        return;
    if (!text) {
        hidePartialTranscript();
        return;
    }
    el.textContent = `Tu: ${text}...`;
    el.classList.remove("hidden");
}
function hidePartialTranscript() {
    document.getElementById("partial-transcript")?.classList.add("hidden");
}
function showDreamingBubble() {
    if (isPinned)
        return; // a vista bloccata il colore dell'avatar segnala gia' il sogno
    isDreamingBubble = true;
    clearHideTimer(); // niente auto-hide: segue lo stato reale del dreaming
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
let isPinned = false;
let exchanges = [];
let currentExchangeIndex = 0;
function buildExchanges(turns) {
    const result = [];
    let pendingQuestion = null;
    for (const turn of turns) {
        if (turn.eventType === "user_message") {
            // Una nuova domanda mentre la precedente non ha ancora risposta: la
            // chiudo comunque come scambio senza risposta, cosi' non si perde.
            if (pendingQuestion !== null)
                result.push({ question: pendingQuestion, answer: "" });
            pendingQuestion = turn.content;
        }
        else {
            result.push({ question: pendingQuestion ?? "", answer: turn.content });
            pendingQuestion = null;
        }
    }
    if (pendingQuestion !== null)
        result.push({ question: pendingQuestion, answer: "" });
    return result;
}
function renderExchange() {
    const posEl = document.getElementById("convo-position");
    const qEl = document.getElementById("convo-question");
    const aEl = document.getElementById("convo-answer");
    const bodyEl = document.getElementById("convo-body");
    if (!posEl || !qEl || !aEl || !bodyEl)
        return;
    if (exchanges.length === 0) {
        qEl.textContent = "";
        aEl.textContent = "Ancora nessuna conversazione.";
        posEl.textContent = "—";
        return;
    }
    currentExchangeIndex = Math.max(0, Math.min(currentExchangeIndex, exchanges.length - 1));
    const ex = exchanges[currentExchangeIndex];
    qEl.textContent = ex.question ? `Tu: ${ex.question}` : "";
    aEl.textContent = ex.answer || "…";
    posEl.textContent = `${currentExchangeIndex + 1} / ${exchanges.length}`;
    // Effetto dissolvenza ad ogni cambio di scambio: riavvio l'animazione
    // togliendo e rimettendo la classe (il reflow forzato in mezzo e' cio' che
    // fa ripartire l'animazione CSS anche sullo stesso elemento).
    bodyEl.classList.remove("fade-in");
    void bodyEl.offsetWidth;
    bodyEl.classList.add("fade-in");
}
async function refreshConvo(jumpToLatest) {
    try {
        const turns = await avatarAPI.getHistory();
        exchanges = buildExchanges(turns);
        if (jumpToLatest || currentExchangeIndex >= exchanges.length) {
            currentExchangeIndex = Math.max(0, exchanges.length - 1);
        }
        renderExchange();
    }
    catch (err) {
        console.error("Caricamento conversazione fallito:", err);
    }
}
function setPinned(pinned) {
    isPinned = pinned;
    document.getElementById("pin-button")?.classList.toggle("active", pinned);
    const view = document.getElementById("convo-view");
    if (pinned) {
        clearHideTimer();
        document.getElementById("bubble")?.classList.add("hidden");
        hidePartialTranscript();
        view?.classList.remove("hidden");
        refreshConvo(true);
    }
    else {
        view?.classList.add("hidden");
    }
}
function initPinButton() {
    const button = document.getElementById("pin-button");
    const closeButton = document.getElementById("convo-close");
    const prevButton = document.getElementById("convo-prev");
    const nextButton = document.getElementById("convo-next");
    if (!button)
        return;
    button.addEventListener("click", (event) => {
        event.stopPropagation();
        setPinned(!isPinned);
    });
    closeButton?.addEventListener("click", (event) => {
        event.stopPropagation();
        setPinned(false);
    });
    prevButton?.addEventListener("click", (event) => {
        event.stopPropagation();
        if (currentExchangeIndex > 0) {
            currentExchangeIndex -= 1;
            renderExchange();
        }
    });
    nextButton?.addEventListener("click", (event) => {
        event.stopPropagation();
        if (currentExchangeIndex < exchanges.length - 1) {
            currentExchangeIndex += 1;
            renderExchange();
        }
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
    initPinButton();
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
