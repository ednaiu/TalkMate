package ru.itmo.talkmate

import android.Manifest
import androidx.test.espresso.Espresso.onView
import androidx.test.espresso.action.ViewActions.scrollTo
import androidx.test.espresso.assertion.ViewAssertions.matches
import androidx.test.espresso.matcher.ViewMatchers.isDisplayed
import androidx.test.espresso.matcher.ViewMatchers.isEnabled
import androidx.test.espresso.matcher.ViewMatchers.withContentDescription
import androidx.test.espresso.matcher.ViewMatchers.withId
import androidx.test.espresso.matcher.ViewMatchers.withText
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.rule.GrantPermissionRule
import org.hamcrest.Matchers.containsString
import org.hamcrest.Matchers.not
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import ru.itmo.talkmate.audio.Recorder
import ru.itmo.talkmate.data.Feedback
import ru.itmo.talkmate.ui.RecordActivity
import ru.itmo.talkmate.ui.ResultsActivity

/** Сценарии тренировки: запись речи, анализ, результаты и рекомендации. */
@RunWith(AndroidJUnit4::class)
class TrainingScenariosTest : BaseUiTest() {

    @get:Rule
    val microphone: GrantPermissionRule = GrantPermissionRule.grant(Manifest.permission.RECORD_AUDIO)

    @Before
    fun openSession() = logIn()

    private fun openResults() = launch<ResultsActivity>(ResultsActivity.intent(context, api.speech))

    // 31
    @Test
    fun recorderStartsIdle() {
        launch(RecordActivity::class.java)
        onView(withId(R.id.tvTimer)).check(matches(withText("00:00.000")))
        onView(withId(R.id.btnStop)).check(matches(not(isEnabled())))
        onView(withId(R.id.btnAnalyze)).check(matches(not(isEnabled())))
        onView(withId(R.id.btnRecordPause)).check(matches(withContentDescription("Начать запись")))
    }

    // 32
    @Test
    fun startRecordingShowsTimerAndEnablesControls() {
        launch(RecordActivity::class.java)
        tap(R.id.btnRecordPause)
        assertEquals(Recorder.State.RECORDING, recorder.state)
        onView(withId(R.id.tvTimer)).check(matches(withText("02:20.000")))
        onView(withId(R.id.tvHint)).check(matches(withText("Идёт запись")))
        onView(withId(R.id.btnStop)).check(matches(isEnabled()))
        onView(withId(R.id.btnAnalyze)).check(matches(isEnabled()))
        onView(withId(R.id.btnRecordPause)).check(matches(withContentDescription("Пауза")))
    }

    // 33
    @Test
    fun pauseAndResumeRecording() {
        launch(RecordActivity::class.java)
        tap(R.id.btnRecordPause)
        tap(R.id.btnRecordPause)
        assertEquals(Recorder.State.PAUSED, recorder.state)
        onView(withId(R.id.tvHint)).check(matches(withText("Запись на паузе")))
        onView(withId(R.id.btnRecordPause)).check(matches(withContentDescription("Продолжить запись")))
        tap(R.id.btnRecordPause)
        assertEquals(Recorder.State.RECORDING, recorder.state)
        onView(withId(R.id.tvHint)).check(matches(withText("Идёт запись")))
    }

    // 34
    @Test
    fun stopKeepsRecordingReadyForAnalysis() {
        launch(RecordActivity::class.java)
        tap(R.id.btnRecordPause)
        tap(R.id.btnStop)
        assertEquals(Recorder.State.STOPPED, recorder.state)
        onView(withId(R.id.tvHint)).check(matches(withText("Запись готова. Нажмите «Анализ»")))
        onView(withId(R.id.btnStop)).check(matches(not(isEnabled())))
        onView(withId(R.id.btnAnalyze)).check(matches(isEnabled()))
    }

    // 35
    @Test
    fun tooShortRecordingIsNotSent() {
        recorder.durationOnStart = 1500
        launch(RecordActivity::class.java)
        tap(R.id.btnRecordPause)
        scrollAndTap(R.id.btnAnalyze)
        onView(withId(R.id.tvHint)).check(matches(withText(containsString("Запись слишком короткая"))))
        onView(withId(R.id.tvTimer)).check(matches(withText("00:00.000")))
        assertEquals(0, api.uploads)
    }

    // 36
    @Test
    fun microphoneFailureIsExplained() {
        recorder.failOnStart = true
        launch(RecordActivity::class.java)
        tap(R.id.btnRecordPause)
        onView(withId(R.id.tvHint)).check(matches(withText("Не удалось включить микрофон")))
        onView(withId(R.id.btnAnalyze)).check(matches(not(isEnabled())))
    }

    // 37. Основной сценарий: записать речь, получить оценки и рекомендации.
    @Test
    fun recordAnalyzeAndSeeResults() {
        launch(RecordActivity::class.java)
        tap(R.id.btnRecordPause)
        tap(R.id.btnStop)
        scrollAndTap(R.id.btnAnalyze)
        assertEquals(1, api.uploads)
        onView(withId(R.id.tvResultsTitle)).check(matches(withText("Результаты")))
        onView(withId(R.id.tvRecommendationsTitle)).check(matches(withText("Рекомендации")))
        onView(withId(R.id.tvRate)).check(matches(withText("250 сл/мин")))
    }

    // 38
    @Test
    fun analysisFailureShowsOoopsAndRetrySucceeds() {
        api.failures.add(FakeApi.server())
        launch(RecordActivity::class.java)
        tap(R.id.btnRecordPause)
        scrollAndTap(R.id.btnAnalyze)
        onView(withId(R.id.tvErrorMessage)).check(matches(withText("Сервис распознавания речи недоступен")))
        tap(R.id.btnRetry)
        assertEquals(1, api.uploads)
        shown(R.id.tvResultsTitle)
    }

    // 39. Значения и подписи как на экране результатов в макете.
    @Test
    fun resultsShowMetricsAndRecommendationFromMockup() {
        openResults()
        onView(withId(R.id.tvRate)).check(matches(withText("250 сл/мин")))
        onView(withId(R.id.tvVolume)).check(matches(withText("тихая")))
        onView(withId(R.id.tvMonotony)).check(matches(withText("выразительная")))
        onView(withId(R.id.tvEmotion)).check(matches(withText("нейтральная")))
        onView(withId(R.id.tvClarity)).check(matches(withText("средняя, 86%")))
        onView(withId(R.id.tvFillers)).check(matches(withText("5 слов")))
        onView(withId(R.id.tvMainIdea)).perform(scrollTo()).check(matches(withText("Сегодня я расскажу о нашем приложении.")))
        onView(withId(R.id.tvKeywords)).check(matches(withText("Ключевые слова: приложение, речь")))
        onView(withId(R.id.tvStructure)).check(matches(withText("частичная")))
        onView(withId(R.id.tvStructureSummary)).check(matches(withText(containsString("заключения нет"))))
        onView(withId(R.id.tvRecTitle)).perform(scrollTo()).check(matches(withText("У вас здорово получается!")))
        onView(withId(R.id.tvRecText)).perform(scrollTo())
            .check(matches(withText("В следующий раз попробуйте увеличить громкость вашего голоса.")))
    }

    @Test
    fun transcriptIsHiddenUntilRequested() {
        openResults()
        onView(withId(R.id.tvTranscript)).check(matches(not(isDisplayed())))
        scrollAndTap(R.id.btnTranscript)
        // Над первой фразой пометка о темпе, над второй об окраске; текст фраз идёт под пометками.
        onView(withId(R.id.tvTranscript)).perform(scrollTo())
            .check(matches(withText("быстро, 212 сл/мин\nНу, вот, сегодня я расскажу\n\nневнятно, 62%  ·  грусть\nо нашем приложении.")))
        onView(withId(R.id.tvTranscriptLegend)).perform(scrollTo())
            .check(matches(withText(containsString("Заполнителей: 2; фраза с темпом вне нормы: 1; невнятная фраза: 1; фраза с отрицательной окраской: 1"))))
        onView(withId(R.id.btnTranscript)).check(matches(withText("Скрыть расшифровку")))
        scrollAndTap(R.id.btnTranscript)
        onView(withId(R.id.tvTranscript)).check(matches(not(isDisplayed())))
        onView(withId(R.id.btnTranscript)).check(matches(withText("Показать расшифровку")))
    }

    @Test
    fun transcriptButtonIsAbsentWhenServerSentNoText() {
        api.speech = api.speech.copy(text = "", segments = emptyList())
        openResults()
        onView(withId(R.id.btnTranscript)).check(matches(not(isDisplayed())))
    }

    // 40
    @Test
    fun resultsForMonotoneSpeechWithoutEmotionAndRecordAgain() {
        api.speech = api.speech.copy(feedback = Feedback(96, "loud", -8.0, "monotone", 0.9, 1, emptyList(), null), content = null)
        openResults()
        onView(withId(R.id.tvRate)).check(matches(withText("96 сл/мин")))
        onView(withId(R.id.tvVolume)).check(matches(withText("громкая")))
        onView(withId(R.id.tvMonotony)).check(matches(withText("монотонная")))
        onView(withId(R.id.tvEmotion)).check(matches(withText("не определена")))
        onView(withId(R.id.tvClarity)).check(matches(withText("не определена")))
        onView(withId(R.id.tvFillers)).check(matches(withText("1 слово")))
        onView(withId(R.id.tvFillerWords)).check(matches(not(isDisplayed())))
        onView(withId(R.id.cardContent)).check(matches(not(isDisplayed())))     // сервер не прислал содержание
        scrollAndTap(R.id.btnAgain)
        onView(withId(R.id.tvTitle)).check(matches(withText("ЗАПИСЬ")))
    }
}
