# DaProdCompanion — abbozzo Android

Primo abbozzo del companion su Android: **nessuna dipendenza dal PC**, il modello gira
interamente sul telefono tramite [MediaPipe LLM Inference](https://ai.google.dev/edge/mediapipe/solutions/genai/llm_inference)
(`com.google.mediapipe:tasks-genai`), stesso approccio "modello a bordo" di progetti come
[jegly/Box](https://github.com/jegly/Box), ma senza vendorizzare/compilare llama.cpp a mano:
Google pubblica gia' un AAR pronto che sa caricare modelli Gemma in formato `.task`.

**Stato**: solo uno scheletro funzionante — una schermata, una chat testuale, nessuna delle
feature del companion desktop (memoria, dreaming, grafo, voce, avatar). Compila e produce un APK
reale (verificato: `gradlew assembleDebug` va a buon fine), ma non e' ancora stato provato su un
dispositivo/emulatore vero con un modello caricato.

## Perche' MediaPipe invece di llama.cpp diretto

`Box` vendorizza `llama.cpp`/`whisper.cpp`/`stable-diffusion.cpp` come submodule e li compila via
NDK — flessibile (qualsiasi GGUF) ma molto piu' lento da mettere in piedi (JNI a mano, build
nativa multi-ABI). MediaPipe ottiene lo stesso risultato pratico richiesto ("modello Gemma
interamente sul telefono, zero dipendenza dal PC") con un semplice `implementation(...)` in
Gradle, nessuna compilazione nativa da parte nostra. Se in futuro serve piu' flessibilita' (un
GGUF qualsiasi, non solo Gemma), l'alternativa llama.cpp resta un cambio di libreria, non di
architettura dell'app.

## Procurarsi il modello (passo manuale, richiesto una volta)

Gemma e' distribuito da Google sotto licenza che richiede accettazione esplicita su Hugging Face
— non e' automatizzabile da riga di comando senza il tuo account:

1. Vai su [huggingface.co/litert-community/Gemma3n-E2B-it](https://huggingface.co/litert-community/Gemma3n-E2B-it),
   accetta la licenza Gemma se richiesto.
2. Scarica il file `.task` (formato MediaPipe, non il `.safetensors`).
3. Con il telefono collegato via USB (debug USB attivo) e l'app gia' installata almeno una volta:

   ```powershell
   adb push gemma3n-e2b.task /sdcard/Android/data/com.daprod.companion/files/gemma3n-e2b.task
   ```

   Il nome del file DEVE essere esattamente `gemma3n-e2b.task` (vedi `MODEL_FILENAME` in
   `MainActivity.kt`) e la cartella e' quella restituita da `getExternalFilesDir(null)` — non
   richiede permessi di storage aggiuntivi perche' e' gia' lo spazio privato dell'app.

## Build

```powershell
cd android
.\gradlew.bat assembleDebug
```

APK in `app/build/outputs/apk/debug/app-debug.apk`. Per installarlo su un dispositivo collegato:

```powershell
adb install app\build\outputs\apk\debug\app-debug.apk
```

## Cosa manca

- Provarlo davvero su un dispositivo (finora solo compilato, mai eseguito: serve un telefono
  Android 12+ di fascia medio-alta, MediaPipe LLM Inference "non supporta in modo affidabile gli
  emulatori" per come Google stessa lo descrive)
- Tutto il resto del companion: memoria persistente, avatar, voce, grafo — questo e' solo la prova
  che l'inferenza locale funziona su questo stack, non ancora un'app completa
- Un modo per scaricare il modello dall'app stessa invece che via `adb push` a mano (complicato
  dal fatto che il file e' dietro licenza Hugging Face)
