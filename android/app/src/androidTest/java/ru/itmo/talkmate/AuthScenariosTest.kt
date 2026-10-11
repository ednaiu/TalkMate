package ru.itmo.talkmate

import android.content.Intent
import androidx.test.espresso.Espresso.onView
import androidx.test.espresso.action.ViewActions.click
import androidx.test.espresso.action.ViewActions.closeSoftKeyboard
import androidx.test.espresso.action.ViewActions.scrollTo
import androidx.test.espresso.action.ViewActions.typeText
import androidx.test.espresso.assertion.ViewAssertions.matches
import androidx.test.espresso.matcher.ViewMatchers.isDisplayed
import androidx.test.espresso.matcher.ViewMatchers.isEnabled
import androidx.test.espresso.matcher.ViewMatchers.isSelected
import androidx.test.espresso.matcher.ViewMatchers.withHint
import androidx.test.espresso.matcher.ViewMatchers.withId
import androidx.test.espresso.matcher.ViewMatchers.withText
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.hamcrest.Matchers.not
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import ru.itmo.talkmate.ui.LoginActivity
import ru.itmo.talkmate.ui.SignUpActivity
import ru.itmo.talkmate.ui.WelcomeActivity

/** Сценарии гостя: приветствие, регистрация, вход. */
@RunWith(AndroidJUnit4::class)
class AuthScenariosTest : BaseUiTest() {

    // 1
    @Test
    fun welcomeShowsLogoAndBothButtons() {
        launch(WelcomeActivity::class.java)
        onView(withId(R.id.tvTalk)).check(matches(withText("Talk")))
        onView(withId(R.id.tvMate)).check(matches(withText("Mate")))
        onView(withId(R.id.btnLogin)).check(matches(withText("Войти")))
        onView(withId(R.id.btnRegistration)).check(matches(withText("Создать аккаунт")))
    }

    // 2
    @Test
    fun loginButtonOpensLoginForm() {
        launch(WelcomeActivity::class.java)
        tap(R.id.btnLogin)
        onView(withId(R.id.tvHello)).check(matches(withText("Войди, чтобы продолжить тренировки")))
        shown(R.id.etEmail)
        shown(R.id.etPassword)
    }

    // 3
    @Test
    fun registrationButtonOpensSignUpForm() {
        launch(WelcomeActivity::class.java)
        tap(R.id.btnRegistration)
        onView(withId(R.id.tvHello)).check(matches(withText("Сохраняй результаты тренировок")))
        onView(withId(R.id.tvTitle)).check(matches(withText("Создать аккаунт")))
        onView(withId(R.id.etName)).check(matches(withHint("Как к тебе обращаться")))
        onView(withId(R.id.etPassword)).check(matches(withHint("Придумай пароль")))
        onView(withId(R.id.etPhone)).check(matches(withHint("+7 …")))
        onView(withId(R.id.etBirthDate)).check(matches(withHint("ДД.ММ.ГГГГ")))
    }

    // 4
    @Test
    fun loggedInUserSkipsWelcome() {
        logIn()
        context.startActivity(Intent(context, WelcomeActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        onView(withId(R.id.tvWelcomeMessage)).check(matches(withText("Привет, Эдна!")))
    }

    // 5. Сценарий из спецификации: регистрация нового пользователя.
    @Test
    fun testRegistration() {
        launch(WelcomeActivity::class.java)
        onView(withId(R.id.btnRegistration)).perform(click())
        onView(withId(R.id.etName)).perform(typeText("John Doe"))
        onView(withId(R.id.etEmail)).perform(typeText("johndoe@example.com"))
        onView(withId(R.id.etPassword)).perform(typeText("password"), closeSoftKeyboard())
        onView(withId(R.id.btnRegister)).perform(scrollTo(), click())
        onView(withId(R.id.tvWelcomeMessage)).check(matches(isDisplayed()))
        onView(withId(R.id.tvWelcomeMessage)).check(matches(withText("Привет, John Doe!")))
        assertTrue(ServiceLocator.session.isLoggedIn)
    }

    // 6
    @Test
    fun registrationRequiresName() {
        launch(SignUpActivity::class.java)
        type(R.id.etEmail, "new@itmo.ru")
        type(R.id.etPassword, "password")
        scrollAndTap(R.id.btnRegister)
        onView(withId(R.id.tvError)).check(matches(withText("Введите имя")))
        assertNull(api.lastRegistration)
    }

    // 7
    @Test
    fun registrationRejectsBadEmail() {
        launch(SignUpActivity::class.java)
        type(R.id.etName, "Эдна")
        type(R.id.etEmail, "not-an-email")
        type(R.id.etPassword, "password")
        scrollAndTap(R.id.btnRegister)
        onView(withId(R.id.tvError)).check(matches(withText("Введите корректный email")))
    }

    // 8
    @Test
    fun registrationRejectsShortPassword() {
        launch(SignUpActivity::class.java)
        type(R.id.etName, "Эдна")
        type(R.id.etEmail, "new@itmo.ru")
        type(R.id.etPassword, "123")
        scrollAndTap(R.id.btnRegister)
        onView(withId(R.id.tvError)).check(matches(withText("Пароль должен быть не короче 6 символов")))
    }

    // 9
    @Test
    fun registrationRejectsBadBirthDate() {
        launch(SignUpActivity::class.java)
        type(R.id.etName, "Эдна")
        type(R.id.etEmail, "new@itmo.ru")
        type(R.id.etPassword, "password")
        type(R.id.etBirthDate, "31.02.2001")
        scrollAndTap(R.id.btnRegister)
        onView(withId(R.id.tvError)).check(matches(withText("Дата рождения в формате ДД.ММ.ГГГГ")))
        assertNull(api.lastRegistration)
    }

    // 10
    @Test
    fun registrationWithTakenEmailShowsServerMessage() {
        launch(SignUpActivity::class.java)
        type(R.id.etName, "Эдна")
        type(R.id.etEmail, "edna@itmo.ru")
        type(R.id.etPassword, "password")
        scrollAndTap(R.id.btnRegister)
        onView(withId(R.id.tvError)).check(matches(withText("Пользователь с таким email уже зарегистрирован")))
        onView(withId(R.id.btnRegister)).check(matches(isEnabled()))
    }

    // 11
    @Test
    fun registrationSendsOptionalFieldsAndGender() {
        launch(SignUpActivity::class.java)
        type(R.id.etName, "Эдна")
        type(R.id.etEmail, "new@itmo.ru")
        type(R.id.etPassword, "password")
        type(R.id.etPhone, "+79990001122")
        type(R.id.etBirthDate, "17.05.2001")
        scrollAndTap(R.id.btnMale)
        scrollAndTap(R.id.btnFemale)
        onView(withId(R.id.btnFemale)).check(matches(isSelected()))
        onView(withId(R.id.btnMale)).check(matches(not(isSelected())))
        scrollAndTap(R.id.btnRegister)
        shown(R.id.tvWelcomeMessage)
        val sent = api.lastRegistration!!
        assertEquals("+79990001122", sent.phone)
        assertEquals("2001-05-17", sent.birthDate)
        assertEquals("female", sent.gender)
    }

    // 12
    @Test
    fun loginWithCorrectPasswordOpensHome() {
        launch(LoginActivity::class.java)
        type(R.id.etEmail, "edna@itmo.ru")
        type(R.id.etPassword, "secret1")
        scrollAndTap(R.id.btnLogin)
        onView(withId(R.id.tvWelcomeMessage)).check(matches(withText("Привет, Эдна!")))
        assertEquals("edna@itmo.ru", ServiceLocator.session.userEmail)
    }

    // 13
    @Test
    fun loginWithWrongPasswordShowsError() {
        launch(LoginActivity::class.java)
        type(R.id.etEmail, "edna@itmo.ru")
        type(R.id.etPassword, "wrong-password")
        scrollAndTap(R.id.btnLogin)
        onView(withId(R.id.tvError)).check(matches(withText("Неверный email или пароль")))
        assertTrue(!ServiceLocator.session.isLoggedIn)
    }

    // 14
    @Test
    fun loginRequiresEmail() {
        launch(LoginActivity::class.java)
        type(R.id.etPassword, "secret1")
        scrollAndTap(R.id.btnLogin)
        onView(withId(R.id.tvError)).check(matches(withText("Введите email")))
    }

    // 15
    @Test
    fun loginWithoutNetworkShowsMessageAndAllowsRetry() {
        api.failures.add(FakeApi.network())
        launch(LoginActivity::class.java)
        type(R.id.etEmail, "edna@itmo.ru")
        type(R.id.etPassword, "secret1")
        scrollAndTap(R.id.btnLogin)
        onView(withId(R.id.tvError)).check(matches(withText("Нет связи с сервером. Проверьте подключение к сети")))
        scrollAndTap(R.id.btnLogin)
        shown(R.id.tvWelcomeMessage)
    }
}
