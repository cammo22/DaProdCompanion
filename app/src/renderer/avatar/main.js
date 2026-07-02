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
function playVoiceAudio(url) {
    const audioEl = document.getElementById("voice-audio");
    if (!audioEl)
        return;
    audioEl.src = url;
    audioEl.play().catch((err) => {
        console.error("Riproduzione audio vocale fallita:", err);
    });
}
function showReplyBubble(payload) {
    isDreamingBubble = false;
    currentBubbleDurationMs = payload.suggestedDurationMs;
    const bubbleEl = document.getElementById("bubble");
    const textEl = document.getElementById("bubble-text");
    const badgeEl = document.getElementById("bubble-badge");
    if (!bubbleEl || !textEl || !badgeEl)
        return;
    textEl.textContent = payload.text;
    badgeEl.classList.toggle("hidden", !payload.usedMemory);
    bubbleEl.classList.remove("hidden");
    // Presente solo per le risposte innescate dalla voce (chat testuale la
    // riproduce gia' nella propria finestra, vedi flashReply in avatar-window.ts).
    if (payload.audioUrl)
        playVoiceAudio(payload.audioUrl);
    scheduleHide(currentBubbleDurationMs);
}
function showDreamingBubble() {
    isDreamingBubble = true;
    clearHideTimer(); // niente auto-hide: segue lo stato reale del dreaming
    const bubbleEl = document.getElementById("bubble");
    const textEl = document.getElementById("bubble-text");
    const badgeEl = document.getElementById("bubble-badge");
    if (!bubbleEl || !textEl || !badgeEl)
        return;
    textEl.textContent = "Sognando...";
    badgeEl.classList.add("hidden");
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
function init() {
    avatarAPI.onStateChange((state) => setState(state));
    avatarAPI.onBubble((payload) => showReplyBubble(payload));
    avatarAPI.onDreamingStart(() => showDreamingBubble());
    avatarAPI.onDreamingEnd(() => hideBubble());
    document.getElementById("avatar")?.addEventListener("click", () => {
        avatarAPI.openChat();
    });
    initMicMuteButton();
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
