/**
 * Script della finestra di onboarding, caricato come modulo ES (<script type="module">)
 * per restare isolato dagli altri script renderer (vedi nota in avatar/main.ts).
 */
export {};

declare const onboardingAPI: {
  getDefaultName(): Promise<string>;
  submitName(name: string): Promise<void>;
};

async function init(): Promise<void> {
  const input = document.getElementById("bot-name-input") as HTMLInputElement;
  const form = document.getElementById("onboarding-form") as HTMLFormElement;

  const defaultName = await onboardingAPI.getDefaultName();
  input.value = defaultName;
  input.focus();
  input.select();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = input.value.trim();
    if (!name) return;
    await onboardingAPI.submitName(name);
  });
}

init();
