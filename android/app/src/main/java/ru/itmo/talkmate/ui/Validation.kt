package ru.itmo.talkmate.ui

import ru.itmo.talkmate.Lang
/** Проверка полей форм до отправки на сервер. Возвращает текст ошибки или null. */
object Validation {
    const val MIN_PASSWORD = 6
    private val EMAIL = Regex("""^[^@\s]+@[^@\s]+\.[^@\s]+$""")

    fun name(value: String) = if (value.isBlank()) Lang.t("Введите имя", "Enter your name") else null

    fun email(value: String) = when {
        value.isBlank() -> Lang.t("Введите email", "Enter your email")
        !EMAIL.matches(value.trim()) -> Lang.t("Введите корректный email", "Enter a valid email")
        else -> null
    }

    fun password(value: String) = when {
        value.isEmpty() -> Lang.t("Введите пароль", "Enter a password")
        value.length < MIN_PASSWORD -> Lang.t("Пароль должен быть не короче $MIN_PASSWORD символов", "The password must be at least $MIN_PASSWORD characters long")
        else -> null
    }

    fun code(value: String) = if (Regex("""^\d{6}$""").matches(value.trim())) null else Lang.t("Введите код из шести цифр", "Enter the six-digit code")

    fun birthDate(value: String) =
        if (value.isBlank() || Formatters.birthDateToIso(value) != null) null else Lang.t("Дата рождения в формате ДД.ММ.ГГГГ", "Date of birth must be DD.MM.YYYY")

    fun serverUrl(value: String) =
        if (Regex("""^https?://[^\s/]+(:\d+)?(/.*)?$""").matches(value.trim())) null else Lang.t("Адрес должен начинаться с http:// или https://", "The address must start with http:// or https://")
}
