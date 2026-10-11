package ru.itmo.talkmate

import android.app.Activity
import android.content.Intent
import androidx.test.core.app.ActivityScenario
import androidx.test.espresso.Espresso.onView
import androidx.test.espresso.ViewInteraction
import androidx.test.espresso.action.ViewActions.click
import androidx.test.espresso.action.ViewActions.closeSoftKeyboard
import androidx.test.espresso.action.ViewActions.replaceText
import androidx.test.espresso.action.ViewActions.scrollTo
import androidx.test.espresso.assertion.ViewAssertions.matches
import androidx.test.espresso.matcher.ViewMatchers.isDisplayed
import androidx.test.espresso.matcher.ViewMatchers.withId
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.Dispatchers
import org.junit.After
import org.junit.Before
import ru.itmo.talkmate.data.AuthResult
import ru.itmo.talkmate.data.User

abstract class BaseUiTest {
    protected lateinit var api: FakeApi
    protected lateinit var recorder: FakeRecorder
    private var scenario: ActivityScenario<*>? = null

    @Before
    fun setUpFakes() {
        // Сценарии написаны для русского интерфейса, а эмулятор по умолчанию английский.
        useLanguage("ru")
        api = FakeApi()
        recorder = FakeRecorder()
        ServiceLocator.api = api
        ServiceLocator.recorderFactory = { recorder }
        // Запросы выполняются сразу в главном потоке, поэтому Espresso видит экран уже обновлённым.
        ServiceLocator.io = Dispatchers.Main.immediate
        ServiceLocator.session.clear()
    }

    @After
    fun tearDown() {
        // Экран к этому моменту мог закрыться сам (например, запись сменилась результатами):
        // сбой при закрытии уже закрытого экрана не должен ронять пройденный сценарий.
        runCatching { scenario?.close() }
        Lang.forced = null
        ServiceLocator.session.clear()
    }

    protected fun useLanguage(tag: String) {
        Lang.forced = tag
        Lang.english = tag != "ru"
    }

    protected fun <T : Activity> launch(activity: Class<T>) {
        scenario = ActivityScenario.launch(activity)
    }

    protected fun <T : Activity> launch(intent: Intent) {
        scenario = ActivityScenario.launch<T>(intent)
    }

    protected fun logIn(name: String = "Эдна", email: String = "edna@itmo.ru") {
        ServiceLocator.session.save(AuthResult("token", User(1, name, email)))
    }

    protected val context get() = InstrumentationRegistry.getInstrumentation().targetContext

    protected fun type(id: Int, text: String) {
        onView(withId(id)).perform(scrollTo(), replaceText(text), closeSoftKeyboard())
    }

    protected fun tap(id: Int): ViewInteraction = onView(withId(id)).perform(click())

    protected fun scrollAndTap(id: Int): ViewInteraction = onView(withId(id)).perform(scrollTo(), click())

    protected fun shown(id: Int): ViewInteraction = onView(withId(id)).check(matches(isDisplayed()))
}
