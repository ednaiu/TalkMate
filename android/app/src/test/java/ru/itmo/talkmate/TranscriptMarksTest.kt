package ru.itmo.talkmate

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import ru.itmo.talkmate.data.ApiParsers
import ru.itmo.talkmate.data.Segment
import ru.itmo.talkmate.data.TextPart
import ru.itmo.talkmate.ui.TranscriptMarks
import ru.itmo.talkmate.ui.TranscriptMarks.Kind
import ru.itmo.talkmate.ui.TranscriptMarks.Mark

class TranscriptMarksTest {
    private fun segment(status: String = "normal", emotion: String? = "neutral", rate: Int = 150, fillers: Int = 0) =
        Segment("текст", rate, status, emotion, List(fillers) { TextPart("ну", true) } + TextPart(" текст", false))

    @Test
    fun calmSegmentHasNoMarks() = assertTrue(TranscriptMarks.marks(segment()).isEmpty())

    @Test
    fun tempoMarks() {
        assertEquals(listOf(Mark("быстро, 212 сл/мин", Kind.TEMPO)), TranscriptMarks.marks(segment("fast", rate = 212)))
        assertEquals(listOf(Mark("медленно, 80 сл/мин", Kind.TEMPO)), TranscriptMarks.marks(segment("slow", rate = 80)))
    }

    @Test
    fun emotionMarks() {
        assertEquals(listOf(Mark("грусть", Kind.NEGATIVE_EMOTION)), TranscriptMarks.marks(segment(emotion = "sadness")))
        assertEquals(listOf(Mark("счастье", Kind.EMOTION)), TranscriptMarks.marks(segment(emotion = "happiness")))
        assertTrue(TranscriptMarks.marks(segment(emotion = null)).isEmpty())
        assertEquals(
            listOf(Mark("быстро, 200 сл/мин", Kind.TEMPO), Mark("злость", Kind.NEGATIVE_EMOTION)),
            TranscriptMarks.marks(segment("fast", "anger", 200)),
        )
    }

    @Test
    fun unclearSegmentIsMarked() {
        val unclear = Segment("текст", 150, "normal", "neutral", listOf(TextPart("текст", false, unclear = true)), 62, "unclear")
        assertEquals(listOf(Mark("невнятно, 62%", Kind.NEGATIVE_EMOTION)), TranscriptMarks.marks(unclear))
        assertTrue(TranscriptMarks.marks(unclear.copy(clarity = 80, clarityLevel = "medium")).isEmpty())
        assertEquals("Невнятная фраза: 1", TranscriptMarks.summary(listOf(unclear, segment())))
    }

    @Test
    fun summary() {
        assertEquals("Замечаний по фразам нет", TranscriptMarks.summary(listOf(segment(), segment(emotion = "happiness"))))
        assertEquals(
            "Заполнителей: 3; фразы с темпом вне нормы: 2; фраза с отрицательной окраской: 1",
            TranscriptMarks.summary(listOf(segment("fast", fillers = 2), segment("slow", "fear", fillers = 1), segment())),
        )
    }

    @Test
    fun segmentsAreParsedFromServerAnswer() {
        val json = JSONObject(
            """{"id":1,"text":"Ну, вот.","feedback":{"speech_rate":150,"volume":"normal","monotony":"expressive","num_fillers":2,"emotion":"neutral"},
               "recommendation":null,
               "segments":[{"start":0.0,"end":4.1,"text":"Ну, вот.","rate":211.6,"rate_status":"fast","emotion":null,
                            "parts":[{"text":"Ну","filler":true},{"text":", ","filler":false},{"text":"вот","filler":true},{"text":".","filler":false}]}]}""",
        )
        val segment = ApiParsers.speech(json).segments.single()
        assertEquals(212, segment.rate)
        assertEquals("fast", segment.rateStatus)
        assertEquals(null, segment.emotion)
        assertEquals(listOf("Ну", "вот"), segment.parts.filter { it.filler }.map { it.text })
        assertEquals(null, segment.clarity)
        assertEquals("Ну, вот.", segment.parts.joinToString("") { it.text })
    }

    @Test
    fun answerWithoutSegmentsStillParses() {
        val json = JSONObject("""{"id":1,"feedback":{"speech_rate":150,"volume":"normal","monotony":"expressive","num_fillers":0,"emotion":null},"recommendation":null}""")
        assertTrue(ApiParsers.speech(json).segments.isEmpty())
    }
}
