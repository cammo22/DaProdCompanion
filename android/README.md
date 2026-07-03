# DaProdCompanion — abbozzo Android

Primo abbozzo del companion su Android: **nessuna dipendenza dal PC**, il modello gira
interamente sul telefono tramite [MediaPipe LLM Inference](https://ai.google.dev/edge/mediapipe/solutions/genai/llm_inference)
(`com.google.mediapipe:tasks-genai`), stesso approccio "modello a bordo" di progetti come
[jegly/Box](https://github.com/jegly/Box), ma senza vendorizzare/compilare llama.cpp a mano:
Google pubblica gia' un AAR pronto che sa caricare modelli Gemma in formato `.task`.

**Stato**: chat testuale con un vero setup iniziale (scarica il modello dall'app stessa al primo
avvio, con barra di avanzamento), ma ancora nessuna delle altre feature del companion desktop
(memoria, dreaming, grafo, voce, avatar). Compila e produce un APK reale (verificato:
`gradlew assembleDebug`/`assembleRelease` vanno a buon fine), ma non e' ancora stato provato su un
dispositivo/emulatore vero con un modello caricato.

## Perche' MediaPipe invece di llama.cpp diretto

`Box` vendorizza `llama.cpp`/`whisper.cpp`/`stable-diffusion.cpp` come submodule e li compila via
NDK — flessibile (qualsiasi GGUF) ma molto piu' lento da mettere in piedi (JNI a mano, build
nativa multi-ABI). MediaPipe ottiene lo stesso risultato pratico richiesto ("modello Gemma
interamente sul telefono, zero dipendenza dal PC") con un semplice `implementation(...)` in
Gradle, nessuna compilazione nativa da parte nostra. Se in futuro serve piu' flessibilita' (un
GGUF qualsiasi, non solo Gemma), l'alternativa llama.cpp resta un cambio di libreria, non di
architettura dell'app.

## Setup iniziale (dall'app, al primo avvio)

Al primo avvio l'app mostra una schermata di setup: incolli il link **diretto** al file `.task`
del modello Gemma e lo scarica da sola, con barra di avanzamento, nella propria cartella privata.
Non serve piu' `adb push` a mano.

Gemma e' distribuito da Google sotto licenza che richiede accettazione esplicita su Hugging Face,
quindi il link diretto non e' hardcodato nell'app (sarebbe un 401 senza il tuo account):

1. Vai su [huggingface.co/litert-community/Gemma3n-E2B-it](https://huggingface.co/litert-community/Gemma3n-E2B-it),
   accetta la licenza Gemma.
2. Copia il link diretto al file `.task` (formato MediaPipe, non il `.safetensors`) — su Hugging
   Face e' il pulsante "download"/"copy download link" del file.
3. Incolla quel link nella schermata di setup dell'app e premi "Scarica il modello".

Se preferisci ancora il metodo manuale (o hai gia' il file), puoi copiarlo a mano con il telefono
collegato via USB:

```powershell
adb push gemma3n-e2b.task /sdcard/Android/data/com.daprod.companion/files/gemma3n-e2b.task
```

Il nome del file sul dispositivo dev'essere `gemma3n-e2b.task` (vedi `ModelManager.kt`), nella
cartella restituita da `getExternalFilesDir(null)` — spazio privato dell'app, nessun permesso di
storage aggiuntivo.

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
- Persistenza della cronologia chat tra un avvio e l'altro (ora e' in memoria, si perde chiudendo)
- Ripresa di un download interrotto (ora un'interruzione riparte da capo)
