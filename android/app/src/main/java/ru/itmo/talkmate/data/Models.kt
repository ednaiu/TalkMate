package ru.itmo.talkmate.data

data class User(val id: Int, val name: String, val email: String, val role: String = "user")

data class AuthResult(val token: String, val user: User)

data class RegisterRequest(
    val name: String,
    val email: String,
    val password: String,
    val phone: String? = null,
    val birthDate: String? = null,
    val gender: String? = null,
)

data class ArticleSummary(val id: Int, val title: String)

data class Article(val id: Int, val title: String, val content: String)

data class Feedback(
    val speechRate: Int,
    val volume: String,
    val volumeDb: Double,
    val monotony: String,
    val pitchVariability: Double,
    val numFillers: Int,
    val fillers: List<String>,
    val emotion: String?,
    /** Чёткость речи в процентах и её уровень: clear, medium, unclear. Пусто, если сервер её не определил. */
    val clarity: Int? = null,
    val clarityLevel: String? = null,
) : java.io.Serializable

/** Кусок текста фразы: обычный или слово-заполнитель. */
data class TextPart(val text: String, val filler: Boolean, val unclear: Boolean = false) : java.io.Serializable

/** Фраза расшифровки со своей оценкой темпа и окраски. */
data class Segment(
    val text: String,
    val rate: Int,
    val rateStatus: String,
    val emotion: String?,
    val parts: List<TextPart>,
    val clarity: Int? = null,
    val clarityLevel: String? = null,
) : java.io.Serializable

/** Содержание выступления: основная мысль (цитата из речи), ключевые слова и оценка структуры. */
data class SpeechContent(
    val mainIdea: String?,
    val keywords: List<String>,
    val structureLevel: String?,
    val structureSummary: String,
) : java.io.Serializable

/** Отметка приложения: с этой секунды записи на экране такой-то слайд. */
data class SlideMark(val page: Int, val start: Double)

/** Один слайд презентации в сравнении с речью. */
data class SlideItem(
    val page: Int,
    val title: String,
    val seconds: Int,
    val coverage: Int?,
    val reading: Int,
    val missed: List<String>,
    val status: String,
    val dense: Boolean,
    val smallText: Boolean,
) : java.io.Serializable

/** Сопоставление речи с презентацией. При ошибке чтения файла заполнено только error. */
data class SlidesReport(
    val pages: Int,
    val coverage: Int?,
    val reading: Int,
    val items: List<SlideItem>,
    val notes: List<String>,
    val error: String? = null,
    /** Время на слайд взято из переключений в приложении, а не оценено по словам. */
    val timed: Boolean = false,
) : java.io.Serializable

data class SpeechResult(
    val id: Int,
    val text: String,
    val duration: Double,
    val feedback: Feedback,
    val recommendationTitle: String,
    val recommendationText: String,
    val segments: List<Segment> = emptyList(),
    val content: SpeechContent? = null,
    val slides: SlidesReport? = null,
) : java.io.Serializable

/** Тренировка в списке: только то, что нужно строке. */
data class TrainingBrief(val id: Int, val title: String, val date: String, val durationSec: Int)

data class TempoPoint(val date: String, val rate: Int)

/** Личный кабинет: счётчики и темп последних тренировок. */
data class Profile(
    val name: String,
    val count: Int,
    val minutes: Int,
    val streak: Int,
    val tempo: List<TempoPoint>,
    val rateSlow: Double,
    val rateFast: Double,
    val recent: List<TrainingBrief>,
)

data class StatPoint(
    val date: String,
    val speechRate: Int,
    val numFillers: Int,
    val volumeDb: Double,
    val pitchVariability: Double,
    val clarity: Int? = null,
)

data class Stats(val points: List<StatPoint>, val thresholds: Map<String, Double>)
