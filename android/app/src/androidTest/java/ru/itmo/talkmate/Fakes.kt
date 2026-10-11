package ru.itmo.talkmate

import ru.itmo.talkmate.audio.Recorder
import ru.itmo.talkmate.data.Api
import ru.itmo.talkmate.data.ApiException
import ru.itmo.talkmate.data.Article
import ru.itmo.talkmate.data.ArticleSummary
import ru.itmo.talkmate.data.AuthResult
import ru.itmo.talkmate.data.Feedback
import ru.itmo.talkmate.data.Profile
import ru.itmo.talkmate.data.TempoPoint
import ru.itmo.talkmate.data.TrainingBrief
import ru.itmo.talkmate.data.RegisterRequest
import ru.itmo.talkmate.data.Segment
import ru.itmo.talkmate.data.SlideMark
import ru.itmo.talkmate.data.SpeechContent
import ru.itmo.talkmate.data.TextPart
import ru.itmo.talkmate.data.SpeechResult
import ru.itmo.talkmate.data.StatPoint
import ru.itmo.talkmate.data.Stats
import ru.itmo.talkmate.data.User
import java.io.File

/** Сервер в памяти. Ошибки из очереди [failures] отдаются по одной на вызов. */
class FakeApi : Api {
    val failures = ArrayDeque<ApiException>()
    val accounts = mutableMapOf("edna@itmo.ru" to ("secret1" to "Эдна"))
    var lastRegistration: RegisterRequest? = null
    var uploads = 0

    var articles = listOf(
        Article(1, "Жестикуляция и движение", "Жестикуляция состоит из пяти основных жестов: **толкание, вытягивание, подъём, бросание и разрывание.** Каждое из них можно выполнить в шести направлениях."),
        Article(2, "Подготовка на площадке", "Приходите в зал за полчаса до начала."),
        Article(3, "Использование презентаций", "Одна мысль на слайд."),
        Article(4, "Разогрев", "Голос работает как мышца."),
    )

    // Значения с экрана результатов из макета.
    var speech = SpeechResult(
        id = 1,
        text = "Ну, вот, сегодня я расскажу о нашем приложении.",
        duration = 60.0,
        feedback = Feedback(250, "quiet", -34.0, "expressive", 3.1, 5, listOf("ну", "вот"), "neutral", 86, "medium"),
        recommendationTitle = "У вас здорово получается!",
        recommendationText = "В следующий раз попробуйте **увеличить громкость** вашего голоса.",
        segments = listOf(
            Segment("Ну, вот, сегодня я расскажу", 212, "fast", "neutral",
                listOf(TextPart("Ну", true), TextPart(", ", false), TextPart("вот", true), TextPart(", сегодня я расскажу", false))),
            Segment("о нашем приложении.", 140, "normal", "sadness",
                listOf(TextPart("о нашем ", false), TextPart("приложении", false, unclear = true), TextPart(".", false)), 62, "unclear"),
        ),
        content = SpeechContent(
            "Сегодня я расскажу о нашем приложении.", listOf("приложение", "речь"), "partial",
            "Вступление есть; мало связок между мыслями (например, во-первых, поэтому); заключения нет: выступление обрывается без вывода.",
        ),
    )

    var stats = Stats(emptyList(), THRESHOLDS)

    private fun maybeFail() {
        failures.removeFirstOrNull()?.let { throw it }
    }

    override fun register(request: RegisterRequest): AuthResult {
        maybeFail()
        if (request.email in accounts) {
            throw ApiException(ApiException.Kind.REJECTED, "Пользователь с таким email уже зарегистрирован", "email_taken")
        }
        lastRegistration = request
        accounts[request.email] = request.password to request.name
        return AuthResult("token", User(2, request.name, request.email))
    }

    override fun login(email: String, password: String): AuthResult {
        maybeFail()
        val account = accounts[email]
        if (account == null || account.first != password) {
            throw ApiException(ApiException.Kind.REJECTED, "Неверный email или пароль", "invalid_credentials")
        }
        return AuthResult("token", User(1, account.second, email))
    }

    val resetRequests = mutableListOf<String>()
    var resetCode = "123456"

    override fun requestPasswordReset(email: String) {
        maybeFail()
        resetRequests += email
    }

    override fun resetPassword(email: String, code: String, newPassword: String): AuthResult {
        maybeFail()
        val account = accounts[email]
        if (account == null || code != resetCode) {
            throw ApiException(ApiException.Kind.REJECTED, "Неверный или просроченный код. Запросите новый", "invalid_code")
        }
        accounts[email] = newPassword to account.second
        return AuthResult("token", User(1, account.second, email))
    }

    override fun articles(): List<ArticleSummary> {
        maybeFail()
        return articles.map { ArticleSummary(it.id, it.title) }
    }

    override fun article(id: Int): Article {
        maybeFail()
        return articles.first { it.id == id }
    }

    override fun uploadSpeech(audio: File, slides: File?, slideMarks: List<SlideMark>?): SpeechResult {
        maybeFail()
        uploads++
        return speech
    }

    var profile = Profile(
        name = "Эдна Юсупова", count = 12, minutes = 86, streak = 4,
        tempo = listOf(TempoPoint("2026-10-02T10:00:00", 118), TempoPoint("2026-10-04T10:00:00", 126), TempoPoint("2026-10-06T10:00:00", 125),
            TempoPoint("2026-10-08T10:00:00", 133), TempoPoint("2026-10-10T10:00:00", 142)),
        rateSlow = 90.0, rateFast = 140.0,
        recent = listOf(TrainingBrief(7, "Подготовка к выступлению", "2026-10-10T10:00:00", 240), TrainingBrief(6, "Самопрезентация", "2026-10-08T10:00:00", 180)),
    )

    override fun profile(): Profile {
        maybeFail()
        return profile
    }

    override fun trainings(): List<TrainingBrief> {
        maybeFail()
        return profile.recent
    }

    override fun speech(id: Int): SpeechResult {
        maybeFail()
        return speech
    }

    override fun stats(): Stats {
        maybeFail()
        return stats
    }

    companion object {
        val THRESHOLDS = mapOf(
            "rate_slow" to 90.0, "rate_fast" to 140.0, "fillers_max" to 4.0,
            "volume_quiet_db" to -30.0, "volume_loud_db" to -12.0, "monotony_min_semitones" to 2.0,
            "clarity_unclear" to 75.0, "clarity_clear" to 88.0,
        )

        fun network() = ApiException(ApiException.Kind.NETWORK, "Нет связи с сервером. Проверьте подключение к сети")
        fun server() = ApiException(ApiException.Kind.SERVER, "Сервис распознавания речи недоступен")
        fun unauthorized() = ApiException(ApiException.Kind.UNAUTHORIZED, "Сессия истекла, войдите снова")

        fun point(day: Int, rate: Int, fillers: Int) =
            StatPoint("2023-05-%02dT10:00:00".format(day), rate, fillers, -20.0 - day, 2.0 + day / 10.0, 80 + day)
    }
}

/** Диктофон без микрофона: длительность записи задаёт тест. */
class FakeRecorder : Recorder {
    override var state = Recorder.State.IDLE
    override var elapsedMs = 0L
    var failOnStart = false
    var durationOnStart = 140_000L
    private var file: File? = null

    override fun start(output: File) {
        if (failOnStart) error("микрофон занят")
        output.writeBytes(ByteArray(64))
        file = output
        elapsedMs = durationOnStart
        state = Recorder.State.RECORDING
    }

    override fun pause() {
        if (state == Recorder.State.RECORDING) state = Recorder.State.PAUSED
    }

    override fun resume() {
        if (state == Recorder.State.PAUSED) state = Recorder.State.RECORDING
    }

    override fun stop(): File? {
        if (state == Recorder.State.RECORDING || state == Recorder.State.PAUSED) state = Recorder.State.STOPPED
        return file
    }

    override fun discard() {
        file?.delete()
        file = null
        elapsedMs = 0
        state = Recorder.State.IDLE
    }
}
