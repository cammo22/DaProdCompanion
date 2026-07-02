/**
 * Client minimo verso l'API nativa di Ollama (non brain_service): serve solo
 * a elencare i modelli gia' scaricati in locale per popolare il menu a tendina
 * nelle Impostazioni, cosi' l'utente sceglie da una lista reale invece di
 * scrivere a mano un tag che potrebbe non esistere o essere scritto male.
 */

export interface OllamaModel {
  name: string;
}

export async function listOllamaModels(ollamaHost: string): Promise<OllamaModel[]> {
  const response = await fetch(`${ollamaHost}/api/tags`);
  if (!response.ok) {
    throw new Error(`Ollama /api/tags ha risposto ${response.status}`);
  }
  const data = (await response.json()) as { models?: { name: string }[] };
  return (data.models ?? []).map((model) => ({ name: model.name }));
}
