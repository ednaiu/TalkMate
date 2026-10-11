package ru.itmo.talkmate

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import ru.itmo.talkmate.ui.Formatters
import ru.itmo.talkmate.ui.Validation

class FormattersTest {
    @Test
    fun rateMatchesMockup() = assertEquals("250 сл/мин", Formatters.rate(250))

    @Test
    fun volumeLabels() {
        assertEquals("тихая", Formatters.volume("quiet"))
        assertEquals("нормальная", Formatters.volume("normal"))
        assertEquals("громкая", Formatters.volume("loud"))
    }

    @Test
    fun emotionLabelsCoverModelClasses() {
        val expected = mapOf(
            "anger" to "злость", "disgust" to "отвращение", "fear" to "страх", "happiness" to "счастье",
            "enthusiasm" to "интерес", "sadness" to "грусть", "neutral" to "нейтральная",
        )
        expected.forEach { (label, text) -> assertEquals(text, Formatters.emotion(label)) }
        assertEquals("не определена", Formatters.emotion(null))
        assertEquals("не определена", Formatters.emotion("surprise"))
    }

    @Test
    fun clarity() {
        assertEquals("чёткая, 95%", Formatters.clarity(95, "clear"))
        assertEquals("средняя, 82%", Formatters.clarity(82, "medium"))
        assertEquals("невнятная, 60%", Formatters.clarity(60, "unclear"))
        assertEquals("не определена", Formatters.clarity(null, null))
    }

    @Test
    fun fillersUseRussianPlurals() {
        assertEquals("0 слов", Formatters.fillers(0))
        assertEquals("1 слово", Formatters.fillers(1))
        assertEquals("3 слова", Formatters.fillers(3))
        assertEquals("5 слов", Formatters.fillers(5))
        assertEquals("11 слов", Formatters.fillers(11))
        assertEquals("14 слов", Formatters.fillers(14))
        assertEquals("21 слово", Formatters.fillers(21))
        assertEquals("22 слова", Formatters.fillers(22))
        assertEquals("111 слов", Formatters.fillers(111))
    }

    @Test
    fun monotonyDescription() {
        assertEquals("монотонная", Formatters.monotonyDescription("monotone"))
        assertEquals("выразительная", Formatters.monotonyDescription("expressive"))
    }

    @Test
    fun timer() {
        assertEquals("00:00.000", Formatters.timer(0))
        assertEquals("00:00.999", Formatters.timer(999))
        assertEquals("00:07.350", Formatters.timer(7_350))
        assertEquals("00:59.000", Formatters.timer(59_000))
        assertEquals("02:20.000", Formatters.timer(140_000))
        assertEquals("61:05.042", Formatters.timer(3_665_042))
    }

    @Test
    fun structureLevels() {
        assertEquals("хорошая", Formatters.structure("good"))
        assertEquals("частичная", Formatters.structure("partial"))
        assertEquals("слабая", Formatters.structure("weak"))
        assertEquals("не оценена", Formatters.structure("short"))
        assertEquals("не оценена", Formatters.structure(null))
    }

    @Test
    fun birthDateConversion() {
        assertEquals("2001-05-17", Formatters.birthDateToIso("17.05.2001"))
        assertEquals("2001-05-07", Formatters.birthDateToIso(" 7.5.2001 "))
        assertEquals("2000-02-29", Formatters.birthDateToIso("29.02.2000"))
        assertNull(Formatters.birthDateToIso("29.02.2001"))
        assertNull(Formatters.birthDateToIso("31.04.2001"))
        assertNull(Formatters.birthDateToIso("17.13.2001"))
        assertNull(Formatters.birthDateToIso("2001-05-17"))
        assertNull(Formatters.birthDateToIso("завтра"))
    }

    @Test
    fun shortDate() {
        assertEquals("07.05", Formatters.shortDate("2023-05-07T10:11:12"))
        assertEquals("мусор", Formatters.shortDate("мусор"))
    }

    @Test
    fun slideLineShowsTimeStatusAndRemarks() {
        assertEquals("0:42 · раскрыт на 80%", Formatters.slideLine(42, "covered", 80, 0, dense = false, smallText = false))
        assertEquals("1:05 · не раскрыт · много текста · мелкий шрифт", Formatters.slideLine(65, "skipped", 5, 0, dense = true, smallText = true))
        assertEquals("0:07 · раскрыт частично на 20% · текст зачитан", Formatters.slideLine(7, "partly", 20, 62, dense = false, smallText = false))
        assertEquals("0:00 · без текста", Formatters.slideLine(0, "no_text", null, 0, dense = false, smallText = false))
        assertEquals("0:30 · пересказан своими словами", Formatters.slideLine(30, "retold", 8, 0, dense = false, smallText = false))
    }

    @Test
    fun englishInterfaceUsesEnglishWords() {
        Lang.english = true
        try {
            assertEquals("115 wpm", Formatters.rate(115))
            assertEquals("quiet", Formatters.volume("quiet"))
            assertEquals("1 word", Formatters.fillers(1))
            assertEquals("5 words", Formatters.fillers(5))
            assertEquals("monotone", Formatters.monotonyDescription("monotone"))
            assertEquals("0:42 · covered 80%", Formatters.slideLine(42, "covered", 80, 0, dense = false, smallText = false))
            assertEquals("0:30 · retold in your own words", Formatters.slideLine(30, "retold", 8, 0, dense = false, smallText = false))
            assertEquals("Enter a valid email", Validation.email("oops"))
        } finally {
            Lang.english = false
        }
        assertEquals("115 сл/мин", Formatters.rate(115))
    }
}
