package ru.itmo.talkmate

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import ru.itmo.talkmate.data.ApiException.Kind
import ru.itmo.talkmate.data.ApiParsers
import ru.itmo.talkmate.data.RegisterRequest

class ApiParsersTest {
    @Test
    fun auth() {
        val result = ApiParsers.auth(JSONObject("""{"token":"abc","user":{"id":7,"name":"Эдна","email":"e@itmo.ru","role":"user"}}"""))
        assertEquals("abc", result.token)
        assertEquals(7, result.user.id)
        assertEquals("Эдна", result.user.name)
    }

    @Test
    fun speechWithFullFeedback() {
        val json = JSONObject(
            """{"id":3,"text":"ну вот","duration":12.5,
               "feedback":{"speech_rate":249.6,"volume":"quiet","volume_db":-34.2,"monotony":"monotone",
                           "pitch_variability":1.1,"num_fillers":5,"fillers":["ну","вот"],"emotion":"neutral"},
               "recommendation":{"id":1,"title":"У вас здорово получается!","description":"**увеличить громкость**"}}""",
        )
        val speech = ApiParsers.speech(json)
        assertEquals(250, speech.feedback.speechRate)
        assertEquals("quiet", speech.feedback.volume)
        assertEquals("monotone", speech.feedback.monotony)
        assertEquals(5, speech.feedback.numFillers)
        assertEquals(listOf("ну", "вот"), speech.feedback.fillers)
        assertEquals("neutral", speech.feedback.emotion)
        assertEquals(null, speech.feedback.clarity)
        assertEquals("У вас здорово получается!", speech.recommendationTitle)
        assertEquals("**увеличить громкость**", speech.recommendationText)
    }

    @Test
    fun speechWithoutEmotionAndRecommendation() {
        val json = JSONObject(
            """{"id":3,"feedback":{"speech_rate":120,"volume":"normal","monotony":"expressive","num_fillers":0,"emotion":null},
               "recommendation":null}""",
        )
        val speech = ApiParsers.speech(json)
        assertNull(speech.feedback.emotion)
        assertTrue(speech.feedback.fillers.isEmpty())
        assertEquals("", speech.recommendationTitle)
    }

    @Test
    fun clarityIsParsedWhenPresent() {
        val json = JSONObject(
            """{"id":3,"feedback":{"speech_rate":120,"volume":"normal","monotony":"expressive","num_fillers":0,"emotion":null,
                                   "clarity":86.4,"clarity_level":"medium"},"recommendation":null,
               "segments":[{"text":"текст","rate":120,"rate_status":"normal","emotion":null,"clarity":62,"clarity_level":"unclear",
                            "parts":[{"text":"текст","filler":false,"unclear":true}]}]}""",
        )
        val speech = ApiParsers.speech(json)
        assertEquals(86, speech.feedback.clarity)
        assertEquals("medium", speech.feedback.clarityLevel)
        assertEquals("unclear", speech.segments.single().clarityLevel)
        assertTrue(speech.segments.single().parts.single().unclear)
        val stats = ApiParsers.stats(JSONObject("""{"points":[{"date":"2026-10-10T10:00:00","speech_rate":120,"num_fillers":0,"clarity":91},
            {"date":"2026-10-09T10:00:00","speech_rate":120,"num_fillers":0,"clarity":null}]}"""))
        assertEquals(listOf(91, null), stats.points.map { it.clarity })
    }

    @Test
    fun contentIsParsed() {
        val json = JSONObject(
            """{"id":3,"feedback":{"speech_rate":120,"volume":"normal","monotony":"expressive","num_fillers":0,"emotion":null},"recommendation":null,
               "content":{"main_idea":"Приложение помогает тренировать выступления.","keywords":["приложение","выступления"],
                          "structure":{"level":"good","intro":true,"links":4,"conclusion":true,"summary":"Вступление есть; логических связок: 4; заключение есть."}}}""",
        )
        val content = ApiParsers.speech(json).content!!
        assertEquals("Приложение помогает тренировать выступления.", content.mainIdea)
        assertEquals(listOf("приложение", "выступления"), content.keywords)
        assertEquals("good", content.structureLevel)
        assertTrue(content.structureSummary.startsWith("Вступление есть"))
        val empty = JSONObject("""{"id":3,"feedback":{"speech_rate":120,"volume":"normal","monotony":"expressive","num_fillers":0,"emotion":null},
            "recommendation":null,"content":{"main_idea":null,"keywords":[],"structure":{"level":"short","intro":null,"links":null,"conclusion":null,"summary":"Запись слишком короткая"}}}""")
        assertEquals(null, ApiParsers.speech(empty).content!!.mainIdea)
        assertEquals(null, ApiParsers.speech(JSONObject("""{"id":3,"feedback":{"speech_rate":120,"volume":"normal","monotony":"expressive","num_fillers":0,"emotion":null},"recommendation":null}""")).content)
    }

    @Test
    fun articles() {
        val list = ApiParsers.articles(JSONArray("""[{"id":1,"title":"Разогрев"},{"id":2,"title":"Жесты"}]"""))
        assertEquals(listOf("Разогрев", "Жесты"), list.map { it.title })
        assertEquals("Текст", ApiParsers.article(JSONObject("""{"id":1,"title":"Разогрев","content":"Текст"}""")).content)
    }

    @Test
    fun stats() {
        val stats = ApiParsers.stats(
            JSONObject(
                """{"count":2,"thresholds":{"rate_slow":120.0,"rate_fast":180.0},
                   "points":[{"date":"2023-05-01T10:00:00","speech_rate":205,"num_fillers":10,"volume_db":-20.5,"pitch_variability":2.4},
                             {"date":"2023-05-02T10:00:00","speech_rate":196,"num_fillers":5,"volume_db":-19.0,"pitch_variability":3.0}]}""",
            ),
        )
        assertEquals(listOf(205, 196), stats.points.map { it.speechRate })
        assertEquals(listOf(10, 5), stats.points.map { it.numFillers })
        assertEquals(120.0, stats.thresholds.getValue("rate_slow"), 0.0)
        assertTrue(ApiParsers.stats(JSONObject("""{"points":[]}""")).points.isEmpty())
    }

    @Test
    fun registerBodySkipsEmptyOptionalFields() {
        val minimal = ApiParsers.registerBody(RegisterRequest("John Doe", "johndoe@example.com", "password", phone = " "))
        assertEquals(setOf("name", "email", "password"), minimal.keySet())
        val full = ApiParsers.registerBody(
            RegisterRequest("Эдна", "e@itmo.ru", "password", phone = "+7999", birthDate = "2001-05-17", gender = "female"),
        )
        assertEquals("2001-05-17", full.getString("birth_date"))
        assertEquals("female", full.getString("gender"))
        assertFalse(full.has("birthDate"))
    }

    @Test
    fun errorsAreClassified() {
        val wrongPassword = ApiParsers.error(401, """{"error":"invalid_credentials","message":"Неверный email или пароль"}""")
        assertEquals(Kind.REJECTED, wrongPassword.kind)
        assertEquals("Неверный email или пароль", wrongPassword.message)

        assertEquals(Kind.UNAUTHORIZED, ApiParsers.error(401, """{"error":"unauthorized","message":"Сессия истекла"}""").kind)
        assertEquals(Kind.REJECTED, ApiParsers.error(409, """{"error":"email_taken","message":"Занято"}""").kind)
        assertEquals(Kind.REJECTED, ApiParsers.error(422, """{"error":"no_speech","message":"Не удалось распознать речь"}""").kind)
        assertEquals(Kind.SERVER, ApiParsers.error(503, """{"error":"recognition_unavailable","message":"Недоступно"}""").kind)

        val html = ApiParsers.error(502, "<html>Bad Gateway</html>")
        assertEquals(Kind.SERVER, html.kind)
        assertTrue(html.message!!.contains("502"))
    }

    @Test
    fun slidesReportIsParsedAndMissingReportStaysNull() {
        val base = """{"id":1,"feedback":{"speech_rate":110,"volume":"normal","monotony":"expressive","num_fillers":0}"""
        assertEquals(null, ApiParsers.speech(JSONObject("$base}")).slides)
        val report = ApiParsers.speech(JSONObject("""$base,"slides":{"pages":2,"coverage":55,"reading":10,"notes":["Слайд 2: мелко"],
            "items":[{"page":1,"title":"Цель","seconds":12,"coverage":80,"reading":0,"missed":[],"status":"covered","dense":false,"small_text":false},
                     {"page":2,"title":"Схема","seconds":0,"coverage":null,"reading":0,"missed":["сервер"],"status":"no_text","dense":true,"small_text":true}]}}""")).slides!!
        assertEquals(2, report.pages)
        assertEquals(55, report.coverage)
        assertEquals(listOf("Слайд 2: мелко"), report.notes)
        assertEquals(null, report.items[1].coverage)
        assertEquals(listOf("сервер"), report.items[1].missed)
        assertEquals(true, report.items[1].smallText)
        val broken = ApiParsers.speech(JSONObject("""$base,"slides":{"error":"Не удалось прочитать презентацию"}}""")).slides!!
        assertEquals("Не удалось прочитать презентацию", broken.error)
    }
}
