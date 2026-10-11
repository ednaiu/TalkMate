package ru.itmo.talkmate.ui

import ru.itmo.talkmate.Lang
/** Тексты для экрана результатов. Чистые функции без Android. */
object Formatters {

    fun rate(wordsPerMinute: Int) = Lang.t("$wordsPerMinute сл/мин", "$wordsPerMinute wpm")

    fun volume(level: String) = when (level) {
        "quiet" -> Lang.t("тихая", "quiet")
        "loud" -> Lang.t("громкая", "loud")
        else -> Lang.t("нормальная", "normal")
    }

    fun slideStatus(status: String) = when (status) {
        "covered" -> Lang.t("раскрыт", "covered")
        "partly" -> Lang.t("раскрыт частично", "partly covered")
        "skipped" -> Lang.t("не раскрыт", "not covered")
        "retold" -> Lang.t("пересказан своими словами", "retold in your own words")
        else -> Lang.t("без текста", "no text")
    }

    /** Время, проведённое на слайде: минуты и секунды. */
    fun slideTime(seconds: Int) = "%d:%02d".format(seconds / 60, seconds % 60)

    /** Вторая строка слайда в сводке: время, оценка и замечания к самому слайду. */
    fun slideLine(seconds: Int, status: String, coverage: Int?, reading: Int, dense: Boolean, smallText: Boolean): String {
        val parts = mutableListOf(slideTime(seconds), slideStatus(status) + if (coverage != null && status in setOf("covered", "partly")) Lang.t(" на $coverage%", " $coverage%") else "")
        if (reading >= 50) parts += Lang.t("текст зачитан", "read aloud")
        if (dense) parts += Lang.t("много текста", "too much text")
        if (smallText) parts += Lang.t("мелкий шрифт", "small font")
        return parts.joinToString(" · ")
    }

    fun monotonyDescription(level: String) = if (level == "monotone") Lang.t("монотонная", "monotone") else Lang.t("выразительная", "expressive")

    fun emotion(label: String?) = when (label) {
        "anger" -> Lang.t("злость", "anger")
        "disgust" -> Lang.t("отвращение", "disgust")
        "fear" -> Lang.t("страх", "fear")
        "happiness" -> Lang.t("счастье", "happiness")
        "enthusiasm" -> Lang.t("интерес", "interest")
        "sadness" -> Lang.t("грусть", "sadness")
        "neutral" -> Lang.t("нейтральная", "neutral")
        else -> Lang.t("не определена", "not detected")
    }

    fun clarity(score: Int?, level: String?): String {
        if (score == null) return Lang.t("не определена", "not detected")
        val word = when (level) {
            "clear" -> Lang.t("чёткая", "clear")
            "unclear" -> Lang.t("невнятная", "unclear")
            else -> Lang.t("средняя", "average")
        }
        return "$word, $score%"
    }

    fun fillers(count: Int) = Lang.t("$count ${plural(count, "слово", "слова", "слов")}", "$count ${if (count == 1) "word" else "words"}")

    fun plural(n: Int, one: String, few: String, many: String): String {
        val mod100 = n % 100
        val mod10 = n % 10
        return when {
            mod100 in 11..14 -> many
            mod10 == 1 -> one
            mod10 in 2..4 -> few
            else -> many
        }
    }

    /** Время записи с миллисекундами: ММ:СС.ммм. */
    fun timer(elapsedMs: Long): String {
        val totalSeconds = elapsedMs / 1000
        return "%02d:%02d.%03d".format(totalSeconds / 60, totalSeconds % 60, elapsedMs % 1000)
    }

    fun structure(level: String?) = when (level) {
        "good" -> Lang.t("хорошая", "good")
        "partial" -> Lang.t("частичная", "partial")
        "weak" -> Lang.t("слабая", "weak")
        else -> Lang.t("не оценена", "not rated")
    }

    /** ГГГГ-ММ-ДД из ввода ДД.ММ.ГГГГ. Возвращает null, если дата не разобрана. */
    fun birthDateToIso(input: String): String? {
        val match = Regex("""^(\d{1,2})\.(\d{1,2})\.(\d{4})$""").find(input.trim()) ?: return null
        val (day, month, year) = match.destructured.toList().map { it.toInt() }
        if (month !in 1..12 || day < 1 || year < 1900) return null
        val leap = year % 4 == 0 && (year % 100 != 0 || year % 400 == 0)
        val daysInMonth = intArrayOf(31, if (leap) 29 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[month - 1]
        if (day > daysInMonth) return null
        return "%04d-%02d-%02d".format(year, month, day)
    }

    /** Короткая подпись даты для оси графика: ДД.ММ из ISO-строки. */
    private val MONTHS_RU = listOf("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря")
    private val MONTHS_EN = listOf("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")

    /** День и месяц из даты сервера: «10 октября», коротко «10 окт». По-английски «October 10» и «Oct 10». */
    fun dayMonth(iso: String, short: Boolean = false): String {
        val match = Regex("""^\d{4}-(\d{2})-(\d{2})""").find(iso) ?: return iso
        val month = match.groupValues[1].toInt().coerceIn(1, 12) - 1
        val day = match.groupValues[2].toInt()
        val name = (if (Lang.english) MONTHS_EN else MONTHS_RU)[month].let { if (short) it.take(3) else it }
        return if (Lang.english) "$name $day" else "$day $name"
    }

    /** Подпись тренировки в списке: дата и длительность. */
    fun trainingMeta(iso: String, durationSec: Int): String {
        val minutes = maxOf(1, Math.round(durationSec / 60f))
        return dayMonth(iso) + " · " + Lang.t("$minutes мин", "$minutes min")
    }

    fun trainingsWord(n: Int) = Lang.t(plural(n, "тренировка", "тренировки", "тренировок"), if (n == 1) "session" else "sessions")

    fun minutesWord(n: Int) = Lang.t(plural(n, "минута практики", "минуты практики", "минут практики"), if (n == 1) "minute of practice" else "minutes of practice")

    fun streakWord(n: Int) = Lang.t(plural(n, "день подряд", "дня подряд", "дней подряд"), if (n == 1) "day in a row" else "days in a row")

    fun lastTrainings(n: Int) = if (n == 1) Lang.t("Последняя тренировка", "Last session")
    else Lang.t("Последние $n ${plural(n, "тренировка", "тренировки", "тренировок")}", "Last $n sessions")

    fun wordsPerMinute(n: Int) = Lang.t(plural(n, "слово в минуту", "слова в минуту", "слов в минуту"), "words per minute")

    fun shortDate(iso: String): String =
        Regex("""^\d{4}-(\d{2})-(\d{2})""").find(iso)?.let { "${it.groupValues[2]}.${it.groupValues[1]}" } ?: iso
}
