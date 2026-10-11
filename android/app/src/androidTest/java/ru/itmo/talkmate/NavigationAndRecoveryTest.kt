package ru.itmo.talkmate

import androidx.test.espresso.Espresso.onView
import androidx.test.espresso.assertion.ViewAssertions.matches
import androidx.test.espresso.contrib.RecyclerViewActions.actionOnItemAtPosition
import androidx.test.espresso.action.ViewActions.click
import androidx.test.espresso.matcher.ViewMatchers.isDisplayed
import androidx.test.espresso.matcher.ViewMatchers.isEnabled
import androidx.test.espresso.matcher.ViewMatchers.withId
import androidx.test.espresso.matcher.ViewMatchers.withText
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.rule.GrantPermissionRule
import androidx.recyclerview.widget.RecyclerView
import org.hamcrest.Matchers.containsString
import org.hamcrest.Matchers.not
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import ru.itmo.talkmate.ui.HomeActivity
import ru.itmo.talkmate.ui.LoginActivity
import ru.itmo.talkmate.ui.WelcomeActivity

/** Кнопка «назад» на экранах и восстановление пароля. */
@RunWith(AndroidJUnit4::class)
class NavigationAndRecoveryTest : BaseUiTest() {

    @get:Rule
    val microphone: GrantPermissionRule = GrantPermissionRule.grant(android.Manifest.permission.RECORD_AUDIO)

    // --- Кнопка «назад» ---

    @Test
    fun backFromLoginAndSignUpReturnsToWelcome() {
        launch(WelcomeActivity::class.java)
        tap(R.id.btnLogin)
        tap(R.id.btnBack)
        shown(R.id.tvMate)
        tap(R.id.btnRegistration)
        tap(R.id.btnBack)
        shown(R.id.tvMate)
    }

    @Test
    fun backFromRecorderArticlesAndStatsReturnsHome() {
        logIn()
        launch(HomeActivity::class.java)
        tap(R.id.cardTraining)
        tap(R.id.btnBack)
        shown(R.id.cardTraining)
        tap(R.id.cardArticles)
        tap(R.id.btnBack)
        shown(R.id.cardTraining)
        scrollAndTap(R.id.cardStats)
        tap(R.id.btnBack)
        shown(R.id.cardTraining)
    }

    @Test
    fun backFromArticleReturnsToListAndFromResultsLeavesScreen() {
        logIn()
        launch(HomeActivity::class.java)
        tap(R.id.cardArticles)
        onView(withId(R.id.rvArticles)).perform(actionOnItemAtPosition<RecyclerView.ViewHolder>(0, click()))
        shown(R.id.tvArticleContent)
        tap(R.id.btnBack)
        shown(R.id.rvArticles)
        tap(R.id.btnBack)
        // До результатов доходим так же, как пользователь: запись, анализ. Назад с результатов ведёт на главный экран.
        tap(R.id.cardTraining)
        tap(R.id.btnRecordPause)
        scrollAndTap(R.id.btnAnalyze)
        shown(R.id.tvRate)
        tap(R.id.btnBack)
        shown(R.id.cardTraining)
    }

    // --- Восстановление пароля ---

    private fun openRecovery(email: String = "edna@itmo.ru") {
        launch(LoginActivity::class.java)
        type(R.id.etEmail, email)
        scrollAndTap(R.id.tvForgot)
    }

    @Test
    fun forgotLinkOpensRecoveryWithTypedEmail() {
        openRecovery()
        onView(withId(R.id.tvHello)).check(matches(withText(containsString("Забыли пароль?"))))
        onView(withId(R.id.etEmail)).check(matches(withText("edna@itmo.ru")))
        onView(withId(R.id.etCode)).check(matches(not(isDisplayed())))
        onView(withId(R.id.btnSendCode)).check(matches(withText("Получить код")))
    }

    @Test
    fun recoveryRequiresValidEmail() {
        openRecovery(email = "")
        scrollAndTap(R.id.btnSendCode)
        onView(withId(R.id.tvError)).check(matches(withText("Введите email")))
        assertTrue(api.resetRequests.isEmpty())
    }

    @Test
    fun requestingCodeShowsSecondStep() {
        openRecovery()
        scrollAndTap(R.id.btnSendCode)
        assertEquals(listOf("edna@itmo.ru"), api.resetRequests)
        onView(withId(R.id.tvInfo)).check(matches(withText(containsString("edna@itmo.ru"))))
        shown(R.id.etCode)
        shown(R.id.etNewPassword)
        onView(withId(R.id.etEmail)).check(matches(not(isEnabled())))
        onView(withId(R.id.btnSendCode)).check(matches(withText("Отправить код ещё раз")))
    }

    @Test
    fun wrongCodeShowsErrorAndKeepsOldPassword() {
        openRecovery()
        scrollAndTap(R.id.btnSendCode)
        type(R.id.etCode, "000000")
        type(R.id.etNewPassword, "newpass1")
        scrollAndTap(R.id.btnResetPassword)
        onView(withId(R.id.tvError)).check(matches(withText("Неверный или просроченный код. Запросите новый")))
        assertEquals("secret1", api.accounts.getValue("edna@itmo.ru").first)
        onView(withId(R.id.btnResetPassword)).check(matches(isEnabled()))
    }

    @Test
    fun codeAndPasswordAreCheckedBeforeSending() {
        openRecovery()
        scrollAndTap(R.id.btnSendCode)
        type(R.id.etCode, "123")
        type(R.id.etNewPassword, "newpass1")
        scrollAndTap(R.id.btnResetPassword)
        onView(withId(R.id.tvError)).check(matches(withText("Введите код из шести цифр")))
        type(R.id.etCode, "123456")
        type(R.id.etNewPassword, "123")
        scrollAndTap(R.id.btnResetPassword)
        onView(withId(R.id.tvError)).check(matches(withText("Пароль должен быть не короче 6 символов")))
        assertEquals("secret1", api.accounts.getValue("edna@itmo.ru").first)
    }

    @Test
    fun correctCodeChangesPasswordAndOpensHome() {
        openRecovery()
        scrollAndTap(R.id.btnSendCode)
        type(R.id.etCode, "123456")
        type(R.id.etNewPassword, "newpass1")
        scrollAndTap(R.id.btnResetPassword)
        onView(withId(R.id.tvWelcomeMessage)).check(matches(withText("Привет, Эдна!")))
        assertEquals("newpass1", api.accounts.getValue("edna@itmo.ru").first)
        assertTrue(ServiceLocator.session.isLoggedIn)
    }

    @Test
    fun recoveryWithoutNetworkShowsMessage() {
        api.failures.add(FakeApi.network())
        openRecovery()
        scrollAndTap(R.id.btnSendCode)
        onView(withId(R.id.tvError)).check(matches(withText("Нет связи с сервером. Проверьте подключение к сети")))
        onView(withId(R.id.etCode)).check(matches(not(isDisplayed())))
        scrollAndTap(R.id.btnSendCode)
        shown(R.id.etCode)
    }
}
