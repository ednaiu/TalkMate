package ru.itmo.talkmate.data

import android.content.Context
import ru.itmo.talkmate.BuildConfig

/** Хранит токен, данные вошедшего пользователя и адрес сервера. */
class SessionStore(context: Context) {
    private val prefs = context.getSharedPreferences("talkmate_session", Context.MODE_PRIVATE)

    val token: String? get() = prefs.getString(KEY_TOKEN, null)
    val isLoggedIn: Boolean get() = !token.isNullOrEmpty()
    val userName: String get() = prefs.getString(KEY_NAME, "").orEmpty()
    val userEmail: String get() = prefs.getString(KEY_EMAIL, "").orEmpty()

    var serverUrl: String
        get() = prefs.getString(KEY_SERVER, null)?.takeIf { it.isNotBlank() } ?: BuildConfig.API_BASE_URL
        set(value) = prefs.edit().putString(KEY_SERVER, value.trim()).apply()

    fun save(result: AuthResult) {
        prefs.edit()
            .putString(KEY_TOKEN, result.token)
            .putString(KEY_NAME, result.user.name)
            .putString(KEY_EMAIL, result.user.email)
            .apply()
    }

    fun clear() {
        prefs.edit().remove(KEY_TOKEN).remove(KEY_NAME).remove(KEY_EMAIL).apply()
    }

    private companion object {
        const val KEY_TOKEN = "token"
        const val KEY_NAME = "name"
        const val KEY_EMAIL = "email"
        const val KEY_SERVER = "server"
    }
}
