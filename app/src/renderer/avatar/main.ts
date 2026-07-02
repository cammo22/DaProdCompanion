/**
 * Script della finestra avatar, caricato come modulo ES (<script type="module">)
 * cosi' resta isolato dagli altri script renderer (avatar/chat/onboarding non
 * condividono mai lo stesso processo, ma tsc compila tutti i file insieme e
 * senza "export" li tratterebbe come un unico scope globale condiviso).
 */
export {};

interface BubblePayload {
  text: string;
  usedMemory: boolean;
  suggestedDurationMs: number;
  audioUrl: string | null;
}

declare const avatarAPI: {
  onStateChange(callback: (state: string) => void): void;
  onBubble(callback: (payload: BubblePayload) => void): void;
  onDreamingStart(callback: () => void): void;
  onDreamingEnd(callback: () => void): void;
  openChat(): void;
  toggleMicMute(): Promise<boolean>;
  getMicMuteState(): Promise<boolean>;
};

// Il timer di auto-nascondimento della bubble vive qui (non nel main
// process) apposta: deve mettersi in pausa quando il mouse ci passa sopra,
// e ripartire da capo quando il mouse esce, come richiesto dall'utente.
let hideTimer: ReturnType<typeof setTimeout> | null = null;
let currentBubbleDurationMs = 8000;
let isDreamingBubble = false;

function setState(state: string): void {
  const avatarEl = document.getElementById("avatar");
  if (avatarEl) avatarEl.dataset.state = state;
}

function clearHideTimer(): void {
  if (hideTimer) {
    clearTimeout(hideTimer);
    hideTimer = null;
  }
}

function hideBubble(): void {
  clearHideTimer();
  document.getElementById("bubble")?.classList.add("hidden");
}

function scheduleHide(durationMs: number): void {
  clearHideTimer();
  hideTimer = setTimeout(hideBubble, durationMs);
}

function playVoiceAudio(url: string): void {
  const audioEl = document.getElementById("voice-audio") as HTMLAudioElement | null;
  if (!audioEl) return;
  audioEl.src = url;
  audioEl.play().catch((err) => {
    console.error("Riproduzione audio vocale fallita:", err);
  });
}

function showReplyBubble(payload: BubblePayload): void {
  isDreamingBubble = false;
  currentBubbleDurationMs = payload.suggestedDurationMs;

  const bubbleEl = document.getElementById("bubble");
  const textEl = document.getElementById("bubble-text");
  const badgeEl = document.getElementById("bubble-badge");
  if (!bubbleEl || !textEl || !badgeEl) return;

  textEl.textContent = payload.text;
  badgeEl.classList.toggle("hidden", !payload.usedMemory);
  bubbleEl.classList.remove("hidden");

  // Presente solo per le risposte innescate dalla voce (chat testuale la
  // riproduce gia' nella propria finestra, vedi flashReply in avatar-window.ts).
  if (payload.audioUrl) playVoiceAudio(payload.audioUrl);

  scheduleHide(currentBubbleDurationMs);
}

function showDreamingBubble(): void {
  isDreamingBubble = true;
  clearHideTimer(); // niente auto-hide: segue lo stato reale del dreaming

  const bubbleEl = document.getElementById("bubble");
  const textEl = document.getElementById("bubble-text");
  const badgeEl = document.getElementById("bubble-badge");
  if (!bubbleEl || !textEl || !badgeEl) return;

  textEl.textContent = "Sognando...";
  badgeEl.classList.add("hidden");
  bubbleEl.classList.remove("hidden");
}

function setMicMuteIcon(muted: boolean): void {
  const button = document.getElementById("mic-mute-button");
  const icon = document.getElementById("mic-mute-icon");
  if (!button || !icon) return;
  icon.textContent = muted ? "🔇" : "🎤";
  button.classList.toggle("muted", muted);
  button.title = muted ? "Microfono mutato: clicca per riattivare" : "Microfono attivo: clicca per mutare";
}

function initMicMuteButton(): void {
  const button = document.getElementById("mic-mute-button");
  if (!button) return;

  avatarAPI.getMicMuteState().then(setMicMuteIcon);

  button.addEventListener("click", (event) => {
    event.stopPropagation(); // non deve anche aprire la chat (click sull'avatar sotto)
    avatarAPI.toggleMicMute().then(setMicMuteIcon);
  });
}

function init(): void {
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
    if (isDreamingBubble) return; // la bubble "sognando" non ha un timer da mettere in pausa
    clearHideTimer();
  });
  bubbleEl?.addEventListener("mouseleave", () => {
    if (isDreamingBubble) return;
    scheduleHide(currentBubbleDurationMs);
  });
}

init();
