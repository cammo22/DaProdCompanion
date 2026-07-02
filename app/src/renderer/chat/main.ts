/**
 * Script della finestra di chat, caricato come modulo ES (<script type="module">)
 * per restare isolato dagli altri script renderer (vedi nota in avatar/main.ts).
 */
export {};

interface ConversationTurn {
  id: number;
  eventType: "user_message" | "bot_reply";
  content: string;
  createdAt: string;
}

interface NewExchangePayload {
  userMessage: string;
  reply: string;
}

declare const chatAPI: {
  sendMessage(message: string): Promise<{ reply: string; audioUrl: string | null }>;
  notifySpeakingStart(): void;
  notifySpeakingEnd(): void;
  getHistory(): Promise<ConversationTurn[]>;
  onNewExchange(callback: (payload: NewExchangePayload) => void): void;
};

let currentAudio: HTMLAudioElement | null = null;

function appendMessage(text: string, sender: "user" | "bot"): void {
  const container = document.getElementById("messages");
  if (!container) return;
  const el = document.createElement("div");
  el.className = `message message-${sender}`;
  el.textContent = text;
  container.appendChild(el);
  container.scrollTop = container.scrollHeight;
}

function setSkipButtonEnabled(enabled: boolean): void {
  const button = document.getElementById("skip-button") as HTMLButtonElement | null;
  if (button) button.disabled = !enabled;
}

function playAudio(url: string): void {
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
    if (currentAudio === audio) currentAudio = null;
  };
  audio.addEventListener("ended", onPlaybackDone, { once: true });
  audio.addEventListener("error", onPlaybackDone, { once: true });
  audio.play().catch((err) => {
    console.error("Riproduzione audio fallita:", err);
    onPlaybackDone();
  });
}

function skipAudio(): void {
  if (!currentAudio) return;
  currentAudio.pause();
  // pause() non genera l'evento 'ended': lo stesso cleanup (smuta il
  // microfono, disabilita il pulsante) va innescato qui a mano.
  chatAPI.notifySpeakingEnd();
  setSkipButtonEnabled(false);
  currentAudio = null;
}

async function loadHistory(): Promise<void> {
  try {
    const turns = await chatAPI.getHistory();
    for (const turn of turns) {
      appendMessage(turn.content, turn.eventType === "user_message" ? "user" : "bot");
    }
  } catch (err) {
    // Puo' succedere al primissimo caricamento in background, prima che
    // brain_service sia pronto: non e' un errore fatale, la finestra resta
    // semplicemente vuota finche' non arriva il primo scambio reale.
    console.warn("Impossibile caricare la cronologia (probabilmente brain_service non e' ancora pronto):", err);
  }
}

function init(): void {
  const form = document.getElementById("chat-form") as HTMLFormElement;
  const input = document.getElementById("chat-input") as HTMLInputElement;
  const skipButton = document.getElementById("skip-button") as HTMLButtonElement;

  loadHistory();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message) return;

    appendMessage(message, "user");
    input.value = "";
    input.disabled = true;

    try {
      const { reply, audioUrl } = await chatAPI.sendMessage(message);
      appendMessage(reply, "bot");
      if (audioUrl) playAudio(audioUrl);
    } catch (err) {
      appendMessage("Errore nel contattare il companion. Riprova.", "bot");
    } finally {
      input.disabled = false;
      input.focus();
    }
  });

  skipButton.addEventListener("click", () => skipAudio());

  // Scambi innescati dalla voce: l'audio lo riproduce gia' l'avatar (vedi
  // handleBrainEvent in index.ts), qui si mostra solo il testo.
  chatAPI.onNewExchange(({ userMessage, reply }) => {
    appendMessage(userMessage, "user");
    appendMessage(reply, "bot");
  });

  input.focus();
}

init();
