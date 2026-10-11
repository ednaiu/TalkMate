package ru.itmo.talkmate.ui

import ru.itmo.talkmate.Lang
import ru.itmo.talkmate.data.Segment

/** Пометки над фразой расшифровки: что в ней не так с темпом и какая слышна окраска. Чистая логика без Android. */
object TranscriptMarks {
    enum class Kind { TEMPO, NEGATIVE_EMOTION, EMOTION }

    data class Mark(val text: String, val kind: Kind)

    private val negative = setOf("anger", "disgust", "fear", "sadness")

    fun marks(segment: Segment): List<Mark> {
        val result = mutableListOf<Mark>()
        when (segment.rateStatus) {
            "fast" -> result += Mark(Lang.t("быстро", "fast") + ", ${Formatters.rate(segment.rate)}", Kind.TEMPO)
            "slow" -> result += Mark(Lang.t("медленно", "slow") + ", ${Formatters.rate(segment.rate)}", Kind.TEMPO)
        }
        if (segment.clarityLevel == "unclear") {
            result += Mark(Lang.t("невнятно", "unclear") + (segment.clarity?.let { ", $it%" } ?: ""), Kind.NEGATIVE_EMOTION)
        }
        val emotion = segment.emotion
        if (emotion != null && emotion != "neutral") {
            result += Mark(Formatters.emotion(emotion), if (emotion in negative) Kind.NEGATIVE_EMOTION else Kind.EMOTION)
        }
        return result
    }

    /** Сколько фраз с замечаниями: для строки-пояснения над расшифровкой. */
    fun summary(segments: List<Segment>): String {
        val tempo = segments.count { it.rateStatus != "normal" }
        val emotion = segments.count { it.emotion in negative }
        val fillers = segments.sumOf { segment -> segment.parts.count { it.filler } }
        val notes = mutableListOf<String>()
        if (fillers > 0) notes += Lang.t("заполнителей: $fillers", "filler words: $fillers")
        if (tempo > 0) notes += Lang.t("${Formatters.plural(tempo, "фраза", "фразы", "фраз")} с темпом вне нормы: $tempo", "phrases with the pace off the norm: $tempo")
        val unclear = segments.count { it.clarityLevel == "unclear" }
        if (unclear > 0) notes += Lang.t("${Formatters.plural(unclear, "невнятная фраза", "невнятные фразы", "невнятных фраз")}: $unclear", "unclear phrases: $unclear")
        if (emotion > 0) notes += Lang.t("${Formatters.plural(emotion, "фраза", "фразы", "фраз")} с отрицательной окраской: $emotion", "phrases with a negative tone: $emotion")
        return if (notes.isEmpty()) Lang.t("Замечаний по фразам нет", "No remarks on the phrases") else notes.joinToString("; ").replaceFirstChar { it.uppercase() }
    }
}
