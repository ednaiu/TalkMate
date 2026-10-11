package ru.itmo.talkmate

import androidx.test.espresso.Espresso.onView
import androidx.test.espresso.Espresso.pressBack
import androidx.test.espresso.assertion.ViewAssertions.matches
import androidx.test.espresso.contrib.RecyclerViewActions.actionOnItemAtPosition
import androidx.test.espresso.contrib.RecyclerViewActions.scrollToPosition
import androidx.test.espresso.action.ViewActions.click
import androidx.test.espresso.action.ViewActions.scrollTo
import androidx.test.espresso.matcher.ViewMatchers.hasDescendant
import androidx.test.espresso.matcher.ViewMatchers.isDisplayed
import androidx.test.espresso.matcher.ViewMatchers.withContentDescription
import androidx.test.espresso.matcher.ViewMatchers.withId
import androidx.test.espresso.matcher.ViewMatchers.withText
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.recyclerview.widget.RecyclerView
import org.hamcrest.Matchers.containsString
import org.hamcrest.Matchers.not
import org.junit.Assert.assertFalse
import org.junit.Test
import org.junit.runner.RunWith
import ru.itmo.talkmate.data.Stats
import ru.itmo.talkmate.ui.ArticlesActivity
import ru.itmo.talkmate.ui.HomeActivity
import ru.itmo.talkmate.ui.StatsActivity

/** Сценарии пользователя: главный экран, статьи, статистика, выход. */
@RunWith(AndroidJUnit4::class)
class HomeScenariosTest : BaseUiTest() {

    private fun openHome() {
        logIn()
        launch(HomeActivity::class.java)
    }

    // 16
    @Test
    fun homeShowsThreeSections() {
        openHome()
        onView(withId(R.id.tvMate)).check(matches(withText("Mate")))
        onView(withId(R.id.cardTraining)).check(matches(hasDescendant(withText("ТРЕНИРОВКА РЕЧИ"))))
        onView(withId(R.id.cardArticles)).check(matches(hasDescendant(withText("Статьи"))))
        onView(withId(R.id.cardStats)).check(matches(hasDescendant(withText("Мой прогресс"))))
        onView(withId(R.id.tvHomeTitle)).check(matches(withText("Говори\nувереннее")))
        onView(withId(R.id.cardTraining)).check(matches(hasDescendant(withText("Запиши выступление и узнай, как улучшить свою речь"))))
        onView(withId(R.id.btnStartTraining)).check(matches(withText("Начать тренировку →")))
    }

    @Test
    fun startTrainingButtonOpensRecorder() {
        openHome()
        tap(R.id.btnStartTraining)
        onView(withId(R.id.tvTitle)).check(matches(withText("ЗАПИСЬ")))
    }

    // 17
    @Test
    fun trainingCardOpensRecorder() {
        openHome()
        tap(R.id.cardTraining)
        onView(withId(R.id.tvTitle)).check(matches(withText("ЗАПИСЬ")))
    }

    // 18
    @Test
    fun articlesCardOpensList() {
        openHome()
        tap(R.id.cardArticles)
        onView(withId(R.id.tvTitle)).check(matches(withText("СТАТЬИ")))
        onView(withText("Жестикуляция и движение")).check(matches(isDisplayed()))
    }

    // 19
    @Test
    fun statsCardOpensStats() {
        openHome()
        scrollAndTap(R.id.cardStats)
        onView(withId(R.id.tvTitle)).check(matches(withText("Stats")))
    }

    // 20
    @Test
    fun profileShowsNameAndEmail() {
        openHome()
        tap(R.id.btnProfile)
        tap(R.id.btnSettings)
        onView(withId(R.id.tvProfileName)).check(matches(withText("Эдна")))
        onView(withId(R.id.tvProfileEmail)).check(matches(withText("edna@itmo.ru")))
    }

    @Test
    fun profileShowsCountersTempoAndRecentTrainings() {
        openHome()
        tap(R.id.navProfile)
        onView(withId(R.id.tvName)).check(matches(withText("Эдна Юсупова")))
        onView(withId(R.id.tvAvatar)).check(matches(withText("Э")))
        onView(withId(R.id.tvCount)).check(matches(withText("12")))
        onView(withId(R.id.tvCountCaption)).check(matches(withText("тренировок")))
        onView(withId(R.id.tvMinutesCaption)).check(matches(withText("минут практики")))
        onView(withId(R.id.tvStreakCaption)).check(matches(withText("дня подряд")))
        onView(withId(R.id.tvTempoValue)).check(matches(withText("142")))
        onView(withId(R.id.tvTempoPeriod)).check(matches(withText("Последние 5 тренировок")))
        onView(withText("Подготовка к выступлению")).perform(scrollTo()).check(matches(isDisplayed()))
        onView(withText("10 октября · 4 мин")).check(matches(isDisplayed()))
    }

    @Test
    fun trainingFromTheListOpensItsResults() {
        openHome()
        tap(R.id.navTrainings)
        onView(withText("Самопрезентация")).perform(click())
        shown(R.id.tvRate)
    }

    // 21
    @Test
    fun logoutReturnsToWelcomeAndClearsSession() {
        openHome()
        tap(R.id.btnProfile)
        tap(R.id.btnSettings)
        onView(withText("Выйти")).perform(click())
        shown(R.id.btnRegistration)
        assertFalse(ServiceLocator.session.isLoggedIn)
    }

    // 22
    @Test
    fun articleListShowsAllTitlesFromServer() {
        logIn()
        launch(ArticlesActivity::class.java)
        listOf("Жестикуляция и движение", "Подготовка на площадке", "Использование презентаций", "Разогрев").forEachIndexed { index, title ->
            onView(withId(R.id.rvArticles)).perform(scrollToPosition<RecyclerView.ViewHolder>(index))
            onView(withText(title)).check(matches(isDisplayed()))
        }
    }

    // 23
    @Test
    fun openingArticleShowsTitleAndTextWithoutMarkup() {
        logIn()
        launch(ArticlesActivity::class.java)
        onView(withId(R.id.rvArticles)).perform(actionOnItemAtPosition<RecyclerView.ViewHolder>(0, click()))
        onView(withId(R.id.tvArticleTitle)).check(matches(withText("Жестикуляция и движение")))
        onView(withId(R.id.tvArticleContent)).check(matches(withText(containsString("толкание, вытягивание, подъём, бросание и разрывание."))))
        onView(withId(R.id.tvArticleContent)).check(matches(not(withText(containsString("**")))))
    }

    // 24
    @Test
    fun backFromArticleReturnsToList() {
        logIn()
        launch(ArticlesActivity::class.java)
        onView(withId(R.id.rvArticles)).perform(actionOnItemAtPosition<RecyclerView.ViewHolder>(1, click()))
        onView(withId(R.id.tvArticleTitle)).check(matches(withText("Подготовка на площадке")))
        pressBack()
        shown(R.id.rvArticles)
    }

    // 25
    @Test
    fun articlesWithoutNetworkShowOoopsAndRetryLoadsList() {
        api.failures.add(FakeApi.network())
        logIn()
        launch(ArticlesActivity::class.java)
        onView(withId(R.id.tvOoops)).check(matches(withText("Ooops…")))
        onView(withId(R.id.tvErrorMessage)).check(matches(withText("Нет связи с сервером. Проверьте подключение к сети")))
        tap(R.id.btnRetry)
        onView(withText("Разогрев")).check(matches(isDisplayed()))
    }

    // 26
    @Test
    fun backArrowOnErrorScreenLeavesBrokenScreen() {
        api.failures.add(FakeApi.network())
        openHome()
        tap(R.id.cardArticles)
        shown(R.id.tvOoops)
        tap(R.id.btnBack)
        shown(R.id.cardTraining)
    }

    // 27
    @Test
    fun statsWithoutRecordingsShowHint() {
        logIn()
        launch(StatsActivity::class.java)
        onView(withId(R.id.tvEmpty)).check(matches(withText(containsString("запишете первое выступление"))))
    }

    // 28
    @Test
    fun statsDrawChartsFromHistory() {
        api.stats = Stats(listOf(FakeApi.point(1, 205, 10), FakeApi.point(2, 196, 5), FakeApi.point(3, 155, 2)), FakeApi.THRESHOLDS)
        logIn()
        launch(StatsActivity::class.java)
        onView(withId(R.id.chartRate)).check(matches(withContentDescription("Оценка скорости (слов/мин): 205, 196, 155")))
        onView(withId(R.id.chartFillers)).check(matches(withContentDescription("Количество слов-заполнителей: 10, 5, 2")))
        onView(withId(R.id.chartVolume)).check(matches(withContentDescription(containsString("Громкость, дБ: -21"))))
        onView(withId(R.id.chartPitch)).check(matches(withContentDescription(containsString("Живость интонации: 2"))))
        onView(withId(R.id.chartClarity)).check(matches(withContentDescription("Чёткость речи, %: 81, 82, 83")))
        onView(withId(R.id.tvEmpty)).check(matches(not(isDisplayed())))
    }

    // 29
    @Test
    fun statsServerErrorShowsOoops() {
        api.failures.add(FakeApi.server())
        logIn()
        launch(StatsActivity::class.java)
        shown(R.id.tvOoops)
        tap(R.id.btnRetry)
        shown(R.id.tvEmpty)
    }

    // 30
    @Test
    fun expiredSessionSendsUserToWelcome() {
        api.failures.add(FakeApi.unauthorized())
        openHome()
        tap(R.id.cardArticles)
        shown(R.id.btnRegistration)
        assertFalse(ServiceLocator.session.isLoggedIn)
    }
}
