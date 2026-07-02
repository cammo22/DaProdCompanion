async function init() {
    const input = document.getElementById("bot-name-input");
    const form = document.getElementById("onboarding-form");
    const defaultName = await onboardingAPI.getDefaultName();
    input.value = defaultName;
    input.focus();
    input.select();
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const name = input.value.trim();
        if (!name)
            return;
        await onboardingAPI.submitName(name);
    });
}
init();
export {};
