package ru.itmo.talkmate

import android.app.Activity
import android.content.Intent
import android.graphics.Bitmap
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.rule.GrantPermissionRule
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import ru.itmo.talkmate.audio.WavRecorder
import ru.itmo.talkmate.data.ApiException
import ru.itmo.talkmate.data.ArticleSummary
import ru.itmo.talkmate.data.RegisterRequest
import ru.itmo.talkmate.ui.ArticleActivity
import ru.itmo.talkmate.ui.ArticlesActivity
import ru.itmo.talkmate.ui.ErrorActivity
import ru.itmo.talkmate.ui.HomeActivity
import ru.itmo.talkmate.ui.LoginActivity
import ru.itmo.talkmate.ui.RecordActivity
import ru.itmo.talkmate.ui.ResetPasswordActivity
import ru.itmo.talkmate.ui.ResultsActivity
import ru.itmo.talkmate.ui.SignUpActivity
import ru.itmo.talkmate.ui.StatsActivity
import ru.itmo.talkmate.ui.WelcomeActivity
import java.io.File

/**
 * Сквозная проверка на живом сервере. Обычный прогон её пропускает; запуск:
 * adb shell am instrument -w -e class ru.itmo.talkmate.RealServerTest -e serverUrl http://10.0.2.2:5050 \
 *     ru.itmo.talkmate.test/androidx.test.runner.AndroidJUnitRunner
 * Снимки экранов складываются в files/shots приложения.
 */
@RunWith(AndroidJUnit4::class)
class RealServerTest {
    @get:Rule
    val microphone: GrantPermissionRule = GrantPermissionRule.grant(android.Manifest.permission.RECORD_AUDIO)

    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext
    private val serverUrl: String? = InstrumentationRegistry.getArguments().getString("serverUrl")
    private var previousUrl: String? = null

    @Before
    fun useRealServer() {
        assumeTrue("serverUrl не задан", serverUrl != null)
        ServiceLocator.init(context)
        ServiceLocator.session.clear()
        previousUrl = ServiceLocator.session.serverUrl
        ServiceLocator.session.serverUrl = serverUrl!!
        useLanguage("ru")
    }

    private fun useLanguage(tag: String) {
        Lang.forced = tag
        Lang.english = tag != "ru"
    }

    @After
    fun restore() {
        previousUrl?.let { ServiceLocator.session.serverUrl = it }
        Lang.forced = null
        ServiceLocator.session.clear()
    }

    private fun <T : Activity> shot(name: String, intent: Intent, waitMs: Long = 1500) {
        ActivityScenario.launch<T>(intent).use {
            Thread.sleep(waitMs)
            val bitmap = instrumentation.uiAutomation.takeScreenshot()
            val folder = File(context.getExternalFilesDir(null), "shots").apply { mkdirs() }
            File(folder, "$name.png").outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        }
    }

    private fun <T : Activity> shot(name: String, activity: Class<T>, waitMs: Long = 1500) = shot<T>(name, Intent(context, activity), waitMs)

    @Test
    fun fullCycleAgainstRealServer() {
        val api = ServiceLocator.api
        val session = ServiceLocator.session

        shot("01_welcome", WelcomeActivity::class.java)
        shot("02_login", LoginActivity::class.java)
        shot("03_signup", SignUpActivity::class.java)
        shot<ResetPasswordActivity>("11_reset", ResetPasswordActivity.intent(context, "edna@itmo.ru"))

        val email = "e2e_${System.currentTimeMillis()}@talkmate.test"
        val registered = api.register(RegisterRequest("Эдна", email, "password", birthDate = "2001-05-17", gender = "female"))
        session.save(registered)
        assertEquals(email, api.login(email, "password").user.email)
        try {
            api.login(email, "wrong-password")
            throw AssertionError("вход с неверным паролем должен быть отклонён")
        } catch (e: ApiException) {
            assertEquals(ApiException.Kind.REJECTED, e.kind)
        }

        val articles = api.articles()
        assertTrue(articles.size >= 4)
        assertEquals("Жестикуляция и движение", articles.first().title)
        assertTrue(api.article(articles.first().id).content.contains("Михаила Чехова"))

        val audio = File(context.cacheDir, "demo_speech.wav")
        instrumentation.context.assets.open("demo_speech.wav").use { input -> audio.outputStream().use { input.copyTo(it) } }
        val result = api.uploadSpeech(audio)
        assertTrue("текст: ${result.text}", result.text.contains("коллеги"))
        assertTrue("темп: ${result.feedback.speechRate}", result.feedback.speechRate in 60..220)
        assertTrue("заполнители: ${result.feedback.numFillers}", result.feedback.numFillers >= 2)
        assertTrue(result.recommendationTitle.isNotBlank() && result.recommendationText.isNotBlank())

        val stats = api.stats()
        assertEquals(1, stats.points.size)
        assertEquals(result.feedback.speechRate, stats.points.single().speechRate)
        assertEquals(90.0, stats.thresholds.getValue("rate_slow"), 0.0)

        shot("04_home", HomeActivity::class.java)
        shot("05_record", RecordActivity::class.java)
        shot<ResultsActivity>("06_results", ResultsActivity.intent(context, result))
        shot("07_articles", ArticlesActivity::class.java)
        shot<ArticleActivity>("08_article", ArticleActivity.intent(context, ArticleSummary(articles.first().id, articles.first().title)))
        api.uploadSpeech(audio)
        shot("09_stats", StatsActivity::class.java)
        val profile = api.profile()
        assertEquals(2, profile.count)
        assertEquals(1, profile.streak)
        assertEquals(result.id, api.speech(result.id).id)
        shot("14_profile", ru.itmo.talkmate.ui.ProfileActivity::class.java, waitMs = 2500)
        shot("15_trainings", ru.itmo.talkmate.ui.TrainingsActivity::class.java, waitMs = 2500)
        shot<ErrorActivity>("10_error", ErrorActivity.intent(context, "Нет связи с сервером. Проверьте подключение к сети"))

        // Презентация. Файлы кладутся в files приложения заранее: -e slidesFile deck.pdf -e talkFile talk.wav.
        val arguments = InstrumentationRegistry.getArguments()
        val deck = arguments.getString("slidesFile")?.let { File(context.getExternalFilesDir(null), it) }
        if (deck != null && deck.exists()) {
            val talk = arguments.getString("talkFile")?.let { File(context.getExternalFilesDir(null), it) } ?: audio
            // Экран записи с презентацией: слайды листаются, номер меняется.
            ActivityScenario.launch<RecordActivity>(Intent(context, RecordActivity::class.java).putExtra(RecordActivity.EXTRA_SLIDES, deck.path)).use { scenario ->
                scenario.onActivity { activity ->
                    repeat(2) { activity.findViewById<android.view.View>(R.id.btnNextSlide).performClick() }
                    assertEquals("Слайд 3 из 17", activity.findViewById<android.widget.TextView>(R.id.tvSlideNumber).text.toString())
                }
                Thread.sleep(1200)
                File(File(context.getExternalFilesDir(null), "shots"), "13_slide_viewer.png").outputStream().use {
                    instrumentation.uiAutomation.takeScreenshot().compress(Bitmap.CompressFormat.PNG, 100, it)
                }
            }
            // Отметки о смене слайдов: сервер берёт время на слайд из них.
            val marks = listOf(ru.itmo.talkmate.data.SlideMark(1, 0.0), ru.itmo.talkmate.data.SlideMark(2, 12.0), ru.itmo.talkmate.data.SlideMark(3, 20.0))
            val timed = api.uploadSpeech(talk, deck, marks).slides ?: throw AssertionError("нет сравнения с презентацией")
            assertTrue("отметки не учтены", timed.timed)
            assertEquals(listOf(12, 8), timed.items.take(2).map { it.seconds })
            val compared = api.uploadSpeech(talk, deck)
            val report = compared.slides ?: throw AssertionError("сервер не вернул сравнение с презентацией")
            assertEquals(null, report.error)
            assertTrue("слайдов: ${report.pages}", report.pages >= 1 && report.items.size == report.pages)
            ActivityScenario.launch<ResultsActivity>(ResultsActivity.intent(context, compared)).use { scenario ->
                scenario.onActivity { activity ->
                    val card = activity.findViewById<android.view.View>(R.id.cardSlides)
                    card.requestRectangleOnScreen(android.graphics.Rect(0, 0, card.width, card.height.coerceAtMost(1600)), true)
                }
                Thread.sleep(1500)
                val bitmap = instrumentation.uiAutomation.takeScreenshot()
                File(File(context.getExternalFilesDir(null), "shots"), "12_slides.png").outputStream().use {
                    bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)
                }
            }
        }

        // Английский интерфейс: те же экраны, статьи и ошибки приходят с сервера по-английски.
        useLanguage("en")
        try {
            assertEquals("Gestures and movement", api.articles().first().title)
            try {
                api.login(email, "wrong-password")
                throw AssertionError("вход с неверным паролем должен быть отклонён")
            } catch (e: ApiException) {
                assertEquals("Wrong email or password", e.message)
            }
            shot("21_welcome_en", WelcomeActivity::class.java)
            shot("22_signup_en", SignUpActivity::class.java)
            shot("23_home_en", HomeActivity::class.java)
            shot("24_record_en", RecordActivity::class.java)
            shot<ResultsActivity>("25_results_en", ResultsActivity.intent(context, result))
            shot("26_articles_en", ArticlesActivity::class.java)
            shot("27_stats_en", StatsActivity::class.java)
        } finally {
            useLanguage("ru")
        }

        // Запись с настоящего диктофона. В эмуляторе микрофон молчит, поэтому сервер вправе ответить
        // «речь не распознана», но сам файл он должен прочитать.
        val recorder = WavRecorder()
        val recorded = File(context.cacheDir, "device.wav")
        recorder.start(recorded)
        Thread.sleep(3500)
        recorder.stop()
        try {
            api.uploadSpeech(recorded)
        } catch (e: ApiException) {
            // no_speech: в записи нет слов; no_signal: микрофон эмулятора отдал ровные нули. Оба ответа значат, что файл прочитан.
            assertTrue("сервер не прочитал запись устройства: ${e.message}", e.code in setOf("no_speech", "no_signal"))
        }

        // С истёкшим токеном сервер отвечает 401, и приложение это различает.
        session.save(registered.copy(token = "broken"))
        try {
            api.stats()
            throw AssertionError("запрос с испорченным токеном должен быть отклонён")
        } catch (e: ApiException) {
            assertEquals(ApiException.Kind.UNAUTHORIZED, e.kind)
        }
    }
}
