package ru.itmo.talkmate.data

import org.json.JSONArray
import ru.itmo.talkmate.Lang
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID

class HttpApi(
    private val baseUrl: () -> String,
    private val token: () -> String?,
) : Api {

    override fun register(request: RegisterRequest): AuthResult =
        ApiParsers.auth(JSONObject(send("POST", "/api/auth/register", ApiParsers.registerBody(request).toString())))

    override fun login(email: String, password: String): AuthResult {
        val body = JSONObject().put("email", email).put("password", password)
        return ApiParsers.auth(JSONObject(send("POST", "/api/auth/login", body.toString())))
    }

    override fun requestPasswordReset(email: String) {
        send("POST", "/api/auth/forgot", JSONObject().put("email", email).toString())
    }

    override fun resetPassword(email: String, code: String, newPassword: String): AuthResult {
        val body = JSONObject().put("email", email).put("code", code).put("password", newPassword)
        return ApiParsers.auth(JSONObject(send("POST", "/api/auth/reset", body.toString())))
    }

    override fun articles(): List<ArticleSummary> = ApiParsers.articles(JSONArray(send("GET", "/api/articles")))

    override fun article(id: Int): Article = ApiParsers.article(JSONObject(send("GET", "/api/articles/$id")))

    override fun stats(): Stats = ApiParsers.stats(JSONObject(send("GET", "/api/stats")))

    override fun profile(): Profile = ApiParsers.profile(JSONObject(send("GET", "/api/profile")))

    override fun trainings(): List<TrainingBrief> = ApiParsers.trainings(JSONArray(send("GET", "/api/trainings")))

    override fun speech(id: Int): SpeechResult = ApiParsers.speech(JSONObject(send("GET", "/api/speeches/$id")))

    override fun uploadSpeech(audio: File, slides: File?, slideMarks: List<SlideMark>?): SpeechResult {
        val boundary = "----talkmate" + UUID.randomUUID().toString().replace("-", "")
        fun head(name: String, filename: String, type: String) =
            ("--$boundary\r\nContent-Disposition: form-data; name=\"$name\"; filename=\"$filename\"\r\n" +
                "Content-Type: $type\r\n\r\n").toByteArray()
        val parts = listOfNotNull(
            head("audio", "speech.wav", "audio/wav") to audio,
            slides?.let { head("slides", "slides.pdf", "application/pdf") to it },
        )
        // Отметки о смене слайдов идут текстовым полем рядом с файлами.
        val marks = slideMarks?.takeIf { it.isNotEmpty() }?.let { list ->
            val json = JSONArray(list.map { JSONObject().put("page", it.page).put("start", it.start) }).toString()
            ("--$boundary\r\nContent-Disposition: form-data; name=\"slide_times\"\r\n\r\n$json\r\n").toByteArray()
        } ?: ByteArray(0)
        val line = "\r\n".toByteArray()
        val tail = "--$boundary--\r\n".toByteArray()
        val response = request("POST", "/api/speeches", readTimeoutMs = ANALYSIS_TIMEOUT_MS) { connection ->
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
            connection.setFixedLengthStreamingMode(parts.sumOf { (head, file) -> head.size + file.length() + line.size } + marks.size + tail.size)
            connection.outputStream.use { out ->
                for ((head, file) in parts) {
                    out.write(head)
                    file.inputStream().use { it.copyTo(out) }
                    out.write(line)
                }
                out.write(marks)
                out.write(tail)
            }
        }
        return ApiParsers.speech(JSONObject(response))
    }

    private fun send(method: String, path: String, json: String? = null): String =
        request(method, path) { connection ->
            if (json != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.outputStream.use { it.write(json.toByteArray()) }
            }
        }

    private fun request(
        method: String,
        path: String,
        readTimeoutMs: Int = READ_TIMEOUT_MS,
        write: (HttpURLConnection) -> Unit,
    ): String {
        val connection = try {
            URL(baseUrl().trimEnd('/') + path).openConnection() as HttpURLConnection
        } catch (e: Exception) {
            throw ApiException(ApiException.Kind.NETWORK, Lang.t("Неверный адрес сервера", "Wrong server address"))
        }
        try {
            connection.requestMethod = method
            connection.connectTimeout = CONNECT_TIMEOUT_MS
            connection.readTimeout = readTimeoutMs
            connection.setRequestProperty("Accept", "application/json")
            connection.setRequestProperty("Accept-Language", Lang.code)
            token()?.let { connection.setRequestProperty("Authorization", "Bearer $it") }
            write(connection)
            val status = connection.responseCode
            val stream = if (status in 200..299) connection.inputStream else connection.errorStream
            val body = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
            if (status !in 200..299) throw ApiParsers.error(status, body)
            return body
        } catch (e: IOException) {
            throw ApiException(ApiException.Kind.NETWORK, Lang.t("Нет связи с сервером. Проверьте подключение к сети", "No connection to the server. Check your network"))
        } catch (e: org.json.JSONException) {
            throw ApiException(ApiException.Kind.SERVER, Lang.t("Сервер вернул непонятный ответ", "The server returned an unreadable response"))
        } finally {
            connection.disconnect()
        }
    }

    private companion object {
        const val CONNECT_TIMEOUT_MS = 10_000
        const val READ_TIMEOUT_MS = 20_000

        // Разбор записи с моделью эмоций на длинном выступлении занимает до нескольких минут.
        const val ANALYSIS_TIMEOUT_MS = 300_000
    }
}
