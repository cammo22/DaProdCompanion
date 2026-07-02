/**
 * Script della finestra di chat, caricato come modulo ES (<script type="module">)
 * per restare isolato dagli altri script renderer (vedi nota in avatar/main.ts).
 */
export {};

declare const chatAPI: {
  sendMessage(message: string): Promise<{ reply: string; audioUrl: string | null }>;
};

function appendMessage(text: string, sender: "user" | "bot"): void {
  const container = document.getElementById("messages");
  if (!container) return;
  const el = document.createElement("div");
  el.className = `message message-${sender}`;
  el.textContent = text;
  container.appendChild(el);
  container.scrollTop = container.scrollHeight;
}

function playAudio(url: string): void {
  const audio = new Audio(url);
  audio.play().catch((err) => {
    console.error("Riproduzione audio fallita:", err);
  });
}

function init(): void {
  const form = document.getElementById("chat-form") as HTMLFormElement;
  const input = document.getElementById("chat-input") as HTMLInputElement;

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

  input.focus();
}

init();
