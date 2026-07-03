package com.daprod.companion

/**
 * Gestione del file del modello sul dispositivo: dove vive, se e' presente,
 * e il download con progresso al primo avvio (setup iniziale).
 *
 * Volutamente senza dipendenze extra (solo java.net): il download di un file
 * grande da un URL diretto non giustifica di aggiungere OkHttp/Ktor. Scarica
 * su un file temporaneo e lo rinomina solo a fine download riuscito, cosi' un
 * download interrotto (app chiusa, rete caduta) non lascia mai un file
 * parziale che verrebbe scambiato per un modello valido al riavvio.
 */

import java.io.File
import java.net.HttpURLConnection
import java.net.URL

class ModelManager(filesDir: File) {

    // Stessa "famiglia" del modello del desktop (Gemma): sul desktop e' Gemma
    // via Ollama, qui e' Gemma on-device in formato .task per MediaPipe.
    val modelFile: File = File(filesDir, "gemma3n-e2b.task")
    private val tempFile: File = File(filesDir, "gemma3n-e2b.task.part")

    fun isModelPresent(): Boolean = modelFile.exists() && modelFile.length() > 0

    /**
     * Scarica il modello dall'URL dato, chiamando [onProgress] con la frazione
     * completata (0f..1f, oppure -1f se la dimensione totale e' sconosciuta).
     * Lancia un'eccezione con un messaggio leggibile in caso di errore.
     */
    fun download(url: String, onProgress: (Float) -> Unit) {
        val connection = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 30_000
            readTimeout = 60_000
            instanceFollowRedirects = true
        }
        try {
            connection.connect()
            if (connection.responseCode !in 200..299) {
                throw IllegalStateException(
                    "Il server ha risposto ${connection.responseCode}. " +
                        "Se il modello e' su Hugging Face, potrebbe richiedere di accettare la " +
                        "licenza Gemma e usare un link diretto autenticato (vedi README).",
                )
            }
            val totalBytes = connection.contentLengthLong
            tempFile.parentFile?.mkdirs()

            connection.inputStream.use { input ->
                tempFile.outputStream().use { output ->
                    val buffer = ByteArray(1 shl 16)
                    var downloaded = 0L
                    while (true) {
                        val read = input.read(buffer)
                        if (read < 0) break
                        output.write(buffer, 0, read)
                        downloaded += read
                        onProgress(if (totalBytes > 0) downloaded.toFloat() / totalBytes else -1f)
                    }
                }
            }

            // Rinomina atomica: solo ora il file "vero" esiste.
            if (modelFile.exists()) modelFile.delete()
            if (!tempFile.renameTo(modelFile)) {
                throw IllegalStateException("Download completato ma impossibile finalizzare il file del modello.")
            }
        } finally {
            connection.disconnect()
            if (tempFile.exists()) tempFile.delete()
        }
    }
}
