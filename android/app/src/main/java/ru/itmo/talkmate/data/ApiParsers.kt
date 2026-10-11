package ru.itmo.talkmate.data

import ru.itmo.talkmate.Lang
import org.json.JSONArray
import org.json.JSONObject

/** Разбор ответов сервера. Без зависимостей от Android, поэтому проверяется обычными модульными тестами. */
object ApiParsers {

    fun auth(json: JSONObject) = AuthResult(json.getString("token"), user(json.getJSONObject("user")))

    fun user(json: JSONObject) = User(
        id = json.getInt("id"),
        name = json.getString("name"),
        email = json.getString("email"),
        role = json.optString("role", "user"),
    )

    fun articles(array: JSONArray): List<ArticleSummary> =
        (0 until array.length()).map { array.getJSONObject(it) }.map { ArticleSummary(it.getInt("id"), it.getString("title")) }

    fun trainings(array: JSONArray?): List<TrainingBrief> =
        (0 until (array?.length() ?: 0)).map { array!!.getJSONObject(it) }.map {
            TrainingBrief(it.getInt("id"), it.optString("title"), it.optString("date"), it.optInt("duration"))
        }

    fun profile(json: JSONObject): Profile {
        val tempo = json.optJSONArray("tempo") ?: JSONArray()
        return Profile(
            name = json.optJSONObject("user")?.optString("name").orEmpty(),
            count = json.optInt("count"),
            minutes = json.optInt("minutes"),
            streak = json.optInt("streak"),
            tempo = (0 until tempo.length()).map { tempo.getJSONObject(it) }.map { TempoPoint(it.optString("date"), it.optInt("rate")) },
            rateSlow = json.optDouble("rate_slow", 90.0),
            rateFast = json.optDouble("rate_fast", 140.0),
            recent = trainings(json.optJSONArray("recent")),
        )
    }

    fun article(json: JSONObject) = Article(json.getInt("id"), json.getString("title"), json.getString("content"))

    fun speech(json: JSONObject): SpeechResult {
        val fb = json.getJSONObject("feedback")
        val rec = json.optJSONObject("recommendation")
        val fillers = fb.optJSONArray("fillers") ?: JSONArray()
        return SpeechResult(
            id = json.getInt("id"),
            text = json.optString("text"),
            duration = json.optDouble("duration", 0.0),
            feedback = Feedback(
                speechRate = Math.round(fb.getDouble("speech_rate")).toInt(),
                volume = fb.getString("volume"),
                volumeDb = fb.optDouble("volume_db", 0.0),
                monotony = fb.getString("monotony"),
                pitchVariability = fb.optDouble("pitch_variability", 0.0),
                numFillers = fb.getInt("num_fillers"),
                fillers = (0 until fillers.length()).map { fillers.getString(it) },
                emotion = if (fb.isNull("emotion")) null else fb.getString("emotion"),
                clarity = optInt(fb, "clarity"),
                clarityLevel = optString(fb, "clarity_level"),
            ),
            recommendationTitle = rec?.optString("title").orEmpty(),
            recommendationText = rec?.optString("description").orEmpty(),
            segments = segments(json.optJSONArray("segments")),
            content = content(json.optJSONObject("content")),
            slides = slides(json.optJSONObject("slides")),
        )
    }

    private fun slides(json: JSONObject?): SlidesReport? {
        if (json == null) return null
        fun strings(array: JSONArray?) = (0 until (array?.length() ?: 0)).map { array!!.getString(it) }
        val items = json.optJSONArray("items") ?: JSONArray()
        return SlidesReport(
            pages = json.optInt("pages"),
            coverage = if (json.isNull("coverage")) null else json.optInt("coverage"),
            reading = json.optInt("reading"),
            items = (0 until items.length()).map { items.getJSONObject(it) }.map { item ->
                SlideItem(
                    page = item.optInt("page"),
                    title = item.optString("title"),
                    seconds = item.optInt("seconds"),
                    coverage = if (item.isNull("coverage")) null else item.optInt("coverage"),
                    reading = item.optInt("reading"),
                    missed = strings(item.optJSONArray("missed")),
                    status = item.optString("status"),
                    dense = item.optBoolean("dense"),
                    smallText = item.optBoolean("small_text"),
                )
            },
            notes = strings(json.optJSONArray("notes")),
            error = optString(json, "error"),
            timed = json.optBoolean("timed"),
        )
    }

    private fun content(json: JSONObject?): SpeechContent? {
        if (json == null) return null
        val keywords = json.optJSONArray("keywords") ?: JSONArray()
        val structure = json.optJSONObject("structure")
        return SpeechContent(
            mainIdea = optString(json, "main_idea"),
            keywords = (0 until keywords.length()).map { keywords.getString(it) },
            structureLevel = structure?.let { optString(it, "level") },
            structureSummary = structure?.optString("summary").orEmpty(),
        )
    }

    private fun segments(array: JSONArray?): List<Segment> {
        if (array == null) return emptyList()
        return (0 until array.length()).map { array.getJSONObject(it) }.map { item ->
            val parts = item.optJSONArray("parts") ?: JSONArray()
            Segment(
                text = item.optString("text"),
                rate = Math.round(item.optDouble("rate", 0.0)).toInt(),
                rateStatus = item.optString("rate_status", "normal"),
                emotion = if (item.isNull("emotion")) null else item.getString("emotion"),
                parts = (0 until parts.length()).map { parts.getJSONObject(it) }
                    .map { TextPart(it.getString("text"), it.optBoolean("filler"), it.optBoolean("unclear")) },
                clarity = optInt(item, "clarity"),
                clarityLevel = optString(item, "clarity_level"),
            )
        }
    }

    fun stats(json: JSONObject): Stats {
        val array = json.getJSONArray("points")
        val points = (0 until array.length()).map { array.getJSONObject(it) }.map {
            StatPoint(
                date = it.getString("date"),
                speechRate = Math.round(it.getDouble("speech_rate")).toInt(),
                numFillers = it.getInt("num_fillers"),
                volumeDb = it.optDouble("volume_db", 0.0),
                pitchVariability = it.optDouble("pitch_variability", 0.0),
                clarity = optInt(it, "clarity"),
            )
        }
        val thresholds = mutableMapOf<String, Double>()
        json.optJSONObject("thresholds")?.let { obj -> obj.keys().forEach { thresholds[it] = obj.getDouble(it) } }
        return Stats(points, thresholds)
    }

    private fun optInt(json: JSONObject, key: String): Int? =
        if (!json.has(key) || json.isNull(key)) null else Math.round(json.getDouble(key)).toInt()

    private fun optString(json: JSONObject, key: String): String? =
        if (!json.has(key) || json.isNull(key)) null else json.getString(key)

    fun registerBody(request: RegisterRequest): JSONObject = JSONObject().apply {
        put("name", request.name)
        put("email", request.email)
        put("password", request.password)
        request.phone?.takeIf { it.isNotBlank() }?.let { put("phone", it) }
        request.birthDate?.takeIf { it.isNotBlank() }?.let { put("birth_date", it) }
        request.gender?.let { put("gender", it) }
    }

    /** Превращает ответ с ошибкой в исключение с текстом, который можно показать пользователю. */
    fun error(status: Int, body: String): ApiException {
        val json = runCatching { JSONObject(body) }.getOrNull()
        val code = json?.optString("error").orEmpty()
        val message = json?.optString("message").orEmpty()
        return when {
            status == 401 && code != "invalid_credentials" ->
                ApiException(ApiException.Kind.UNAUTHORIZED, message.ifEmpty { Lang.t("Войдите снова", "Please log in again") }, code)
            status in 400..499 ->
                ApiException(ApiException.Kind.REJECTED, message.ifEmpty { Lang.t("Запрос отклонён ($status)", "Request rejected ($status)") }, code)
            else -> ApiException(ApiException.Kind.SERVER, message.ifEmpty { Lang.t("Сервер недоступен ($status)", "Server unavailable ($status)") }, code)
        }
    }
}
