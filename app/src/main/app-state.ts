/**
 * Stato condiviso minimo tra moduli main, per evitare dipendenze circolari:
 * chat-window.ts deve sapere se l'app sta davvero chiudendo (per lasciar
 * procedere la chiusura della finestra invece di limitarsi a nasconderla),
 * ma index.ts importa gia' da chat-window.ts, quindi l'import inverso
 * creerebbe un ciclo.
 */

let quitting = false;

export function isAppQuitting(): boolean {
  return quitting;
}

export function markAppQuitting(): void {
  quitting = true;
}
