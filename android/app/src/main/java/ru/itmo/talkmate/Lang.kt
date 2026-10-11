package ru.itmo.talkmate

import android.content.Context
import android.content.res.Configuration
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat
import java.util.Locale

/**
 * Язык интерфейса: русский или английский. Строки вёрстки берутся из ресурсов, а тексты, которые собираются
 * в коде, выбираются функцией [t]. Язык задаётся в профиле либо в настройках телефона; всё, что не русский,
 * показывается по-английски.
 */
object Lang {
    @Volatile
    var english = false

    /** Язык, заданный в обход настроек: так автотесты получают один и тот же язык на любом устройстве. */
    @Volatile
    var forced: String? = null

    /** Код языка для сервера: на нём он пишет рекомендации и сообщения об ошибках. */
    val code get() = if (english) "en" else "ru"

    fun t(russian: String, english: String) = if (this.english) english else russian

    /** Контекст экрана с принудительно заданным языком или исходный, если язык не задан. */
    fun wrap(base: Context): Context {
        val tag = forced ?: return base
        val configuration = Configuration(base.resources.configuration)
        configuration.setLocale(Locale.forLanguageTag(tag))
        return base.createConfigurationContext(configuration)
    }

    /** Запоминает язык, с которым открыт экран. */
    fun sync(context: Context) {
        english = context.resources.configuration.locales[0].language != "ru"
    }

    /** Язык, выбранный в приложении: ru, en или null, если приложение следует за системой. */
    fun chosen(): String? = AppCompatDelegate.getApplicationLocales().takeIf { !it.isEmpty }?.get(0)?.language

    fun choose(tag: String?) {
        AppCompatDelegate.setApplicationLocales(
            if (tag == null) LocaleListCompat.getEmptyLocaleList() else LocaleListCompat.forLanguageTags(tag),
        )
    }
}
