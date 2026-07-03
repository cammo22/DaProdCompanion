package com.daprod.companion

/**
 * Companion su Android: nessuna dipendenza dal PC, il modello (Gemma, stessa
 * famiglia del desktop) gira interamente sul telefono tramite MediaPipe LLM
 * Inference. Rispetto al primo abbozzo ha ora un vero setup iniziale: se il
 * modello non e' presente, lo si scarica dall'app stessa con una barra di
 * avanzamento, invece di doverlo copiare a mano via adb.
 *
 * Ancora solo chat testuale: le altre feature del companion desktop (memoria,
 * dreaming, grafo, voce, avatar) non ci sono qui. Ma il percorso primo-avvio
 * -> modello pronto -> conversazione e' completo e autonomo.
 */

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.google.mediapipe.tasks.genai.llminference.LlmInference
import com.google.mediapipe.tasks.genai.llminference.LlmInference.LlmInferenceOptions
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val modelManager = ModelManager(getExternalFilesDir(null) ?: filesDir)
        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    CompanionScreen(modelManager)
                }
            }
        }
    }
}

private sealed interface AppState {
    data object NeedsSetup : AppState
    data class Downloading(val progress: Float) : AppState
    data object LoadingModel : AppState
    data class Ready(val engine: LlmInference) : AppState
    data class Failed(val message: String) : AppState
}

private data class ChatMessage(val text: String, val fromUser: Boolean)

@Composable
private fun CompanionScreen(modelManager: ModelManager) {
    val context = LocalContext.current
    var state by remember {
        mutableStateOf<AppState>(if (modelManager.isModelPresent()) AppState.LoadingModel else AppState.NeedsSetup)
    }
    var messages by remember { mutableStateOf(listOf<ChatMessage>()) }
    val scope = rememberCoroutineScope()

    if (state is AppState.LoadingModel) {
        LaunchedEffect(Unit) {
            state = try {
                val options = LlmInferenceOptions.builder()
                    .setModelPath(modelManager.modelFile.absolutePath)
                    .setMaxTopK(64)
                    .build()
                val engine = withContext(Dispatchers.IO) { LlmInference.createFromOptions(context, options) }
                AppState.Ready(engine)
            } catch (e: Exception) {
                AppState.Failed(e.message ?: "Errore sconosciuto nel caricamento del modello")
            }
        }
    }

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text("DaProdCompanion", style = MaterialTheme.typography.titleLarge)
        Spacer(Modifier.height(12.dp))

        when (val current = state) {
            is AppState.NeedsSetup -> SetupScreen(
                onDownload = { url ->
                    scope.launch {
                        state = AppState.Downloading(0f)
                        state = try {
                            withContext(Dispatchers.IO) {
                                modelManager.download(url) { p ->
                                    scope.launch { state = AppState.Downloading(p) }
                                }
                            }
                            AppState.LoadingModel
                        } catch (e: Exception) {
                            AppState.Failed(e.message ?: "Download fallito")
                        }
                    }
                },
            )
            is AppState.Downloading -> DownloadingScreen(current.progress)
            is AppState.LoadingModel -> Row(verticalAlignment = Alignment.CenterVertically) {
                CircularProgressIndicator()
                Text("  Carico il modello sul dispositivo...")
            }
            is AppState.Failed -> Column {
                Text("Qualcosa e' andato storto:", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(8.dp))
                Text(current.message)
                Spacer(Modifier.height(16.dp))
                Button(onClick = { state = AppState.NeedsSetup }) { Text("Riprova il setup") }
            }
            is AppState.Ready -> ChatArea(messages) { userText ->
                messages = messages + ChatMessage(userText, fromUser = true)
                scope.launch {
                    val reply = withContext(Dispatchers.IO) { current.engine.generateResponse(userText) }
                    messages = messages + ChatMessage(reply, fromUser = false)
                }
            }
        }
    }
}

@Composable
private fun ColumnScope.SetupScreen(onDownload: (String) -> Unit) {
    var url by remember { mutableStateOf("") }

    Text("Primo avvio: serve il modello", style = MaterialTheme.typography.titleMedium)
    Spacer(Modifier.height(8.dp))
    Text(
        "Il companion usa un modello Gemma che gira interamente sul telefono (come sul desktop, " +
            "ma qui a bordo). Va scaricato una volta sola.\n\n" +
            "Incolla qui il link DIRETTO al file del modello (.task per MediaPipe). " +
            "I modelli Gemma sono su Hugging Face e richiedono di accettare la licenza: " +
            "una volta accettata, copia il link diretto al file .task del modello Gemma 3n E2B.",
    )
    Spacer(Modifier.height(12.dp))
    OutlinedTextField(
        value = url,
        onValueChange = { url = it },
        modifier = Modifier.fillMaxWidth(),
        label = { Text("URL diretto al modello .task") },
        singleLine = true,
    )
    Spacer(Modifier.height(12.dp))
    Button(
        onClick = { onDownload(url.trim()) },
        enabled = url.isNotBlank(),
    ) { Text("Scarica il modello") }
}

@Composable
private fun ColumnScope.DownloadingScreen(progress: Float) {
    Text("Scarico il modello...", style = MaterialTheme.typography.titleMedium)
    Spacer(Modifier.height(12.dp))
    if (progress >= 0f) {
        LinearProgressIndicator(progress = { progress }, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(8.dp))
        Text("${(progress * 100).toInt()}%")
    } else {
        LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
        Text("Dimensione sconosciuta, attendi...")
    }
    Spacer(Modifier.height(8.dp))
    Text("Puo' richiedere qualche minuto e alcuni GB di spazio. Tieni l'app aperta.")
}

@Composable
private fun ColumnScope.ChatArea(messages: List<ChatMessage>, onSend: (String) -> Unit) {
    var input by remember { mutableStateOf("") }

    LazyColumn(
        modifier = Modifier.fillMaxWidth().weight(1f, fill = true),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(messages) { message ->
            Text(if (message.fromUser) "Tu: ${message.text}" else "Companion: ${message.text}")
        }
    }

    Row(modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
        OutlinedTextField(value = input, onValueChange = { input = it }, modifier = Modifier.weight(1f))
        Button(onClick = {
            if (input.isNotBlank()) {
                onSend(input)
                input = ""
            }
        }) { Text("Invia") }
    }
}
