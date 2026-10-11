package ru.itmo.talkmate.data

import java.io.File

/** Все методы блокирующие и бросают [ApiException]. Вызывать не из главного потока. */
interface Api {
    fun register(request: RegisterRequest): AuthResult
    fun login(email: String, password: String): AuthResult

    /** Просит сервер выслать код восстановления. Ответ одинаков для любого адреса. */
    fun requestPasswordReset(email: String)

    /** Меняет пароль по коду из письма и сразу входит в систему. */
    fun resetPassword(email: String, code: String, newPassword: String): AuthResult
    fun articles(): List<ArticleSummary>
    fun article(id: Int): Article
    /** Отправляет запись на разбор. Презентацию в PDF можно приложить, тогда сервер сравнит её с речью. */
    fun uploadSpeech(audio: File, slides: File? = null, slideMarks: List<SlideMark>? = null): SpeechResult
    fun stats(): Stats
    fun profile(): Profile

    /** Все тренировки коротко, новые сверху. */
    fun trainings(): List<TrainingBrief>

    /** Разбор одной тренировки целиком: по нему открывается экран результатов. */
    fun speech(id: Int): SpeechResult
}
