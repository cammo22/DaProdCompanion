package com.daprod.companion

/**
 * Abbozzo minimo del companion su Android: nessuna dipendenza dal PC, il
 * modello (Gemma 3n E2B in formato .task) gira interamente sul telefono
 * tramite MediaPipe LLM Inference. Non ha ancora niente delle feature del
 * companion desktop (memoria, dreaming, grafo, voce): e' solo la base che
 * dimostra che l'inferenza locale funziona davvero su questo hardware, prima
 * di costruirci sopra il resto.
 *
 * Il modello NON e' incluso nell'apk (troppo grande, ed e' distribuito da
 * Google sotto licenza Gemma su HuggingFace, che richiede accettazione
 * esplicita): va copiato a mano sul dispositivo, vedi README.md in questa
 * cartella per le istruzioni precise.
 */

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
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
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private const val MODEL_FILENAME = "gemma3n-e2b.task"

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    CompanionScreen(modelFile = File(getExternalFilesDir(null), MODEL_FILENAME))
                }
            }
        }
    }
}

private sealed interface LlmState {
    data object MissingModel : LlmState
    data object Loading : LlmState
    data class Ready(val engine: LlmInference) : LlmState
    data class Failed(val message: String) : LlmState
}

private data class ChatMessage(val text: String, val fromUser: Boolean)

@Composable
private fun CompanionScreen(modelFile: File) {
    val context = LocalContext.current
    var state by remember { mutableStateOf<LlmState>(if (modelFile.exists()) LlmState.Loading else LlmState.MissingModel) }
    var messages by remember { mutableStateOf(listOf<ChatMessage>()) }
    val scope = rememberCoroutineScope()

    if (state is LlmState.Loading) {
        LaunchedEffect(modelFile) {
            state = try {
                val options = LlmInferenceOptions.builder()
                    .setModelPath(modelFile.absolutePath)
                    .setMaxTopK(64)
                    .build()
                val engine = withContext(Dispatchers.IO) {
                    LlmInference.createFromOptions(context, options)
                }
                LlmState.Ready(engine)
            } catch (e: Exception) {
                LlmState.Failed(e.message ?: "Errore sconosciuto nel caricamento del modello")
            }
        }
    }

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text("DaProdCompanion — abbozzo Android", style = MaterialTheme.typography.titleMedium)

        when (val current = state) {
            is LlmState.MissingModel -> Text(
                "Modello non trovato in:\n${modelFile.absolutePath}\n\nVedi README.md per come procurarlo e copiarlo sul dispositivo.",
            )
            is LlmState.Loading -> Row(verticalAlignment = Alignment.CenterVertically) {
                CircularProgressIndicator()
                Text(" Carico il modello...")
            }
            is LlmState.Failed -> Text("Caricamento fallito: ${current.message}")
            is LlmState.Ready -> ChatArea(messages = messages) { userText ->
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
