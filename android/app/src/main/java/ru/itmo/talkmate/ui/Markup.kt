package ru.itmo.talkmate.ui

import android.graphics.Typeface
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.style.ForegroundColorSpan
import android.text.style.StyleSpan

/** Разметка текстов статей и рекомендаций: фрагмент между ** и ** выделяется жирным. */
object Markup {
    data class Segment(val text: String, val bold: Boolean)

    fun parse(source: String): List<Segment> {
        val parts = source.split("**")
        // Непарная пара звёздочек: считаем текст обычным, чтобы не потерять символы.
        if (parts.size % 2 == 0) return listOf(Segment(source, false))
        return parts.mapIndexedNotNull { index, text ->
            if (text.isEmpty()) null else Segment(text, bold = index % 2 == 1)
        }
    }

    fun plain(source: String): String = parse(source).joinToString("") { it.text }

    fun render(source: String, boldColor: Int): CharSequence {
        val builder = SpannableStringBuilder()
        for (segment in parse(source)) {
            val start = builder.length
            builder.append(segment.text)
            if (segment.bold) {
                builder.setSpan(StyleSpan(Typeface.BOLD), start, builder.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                builder.setSpan(ForegroundColorSpan(boldColor), start, builder.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            }
        }
        return builder
    }
}
