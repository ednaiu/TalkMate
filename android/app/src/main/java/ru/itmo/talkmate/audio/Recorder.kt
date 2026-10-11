package ru.itmo.talkmate.audio

import java.io.File

interface Recorder {
    enum class State { IDLE, RECORDING, PAUSED, STOPPED }

    val state: State

    /** Сколько звука уже записано, без учёта пауз. */
    val elapsedMs: Long

    /** Начинает запись в файл. Бросает исключение, если микрофон недоступен. */
    fun start(output: File)
    fun pause()
    fun resume()

    /** Завершает запись и возвращает готовый файл. */
    fun stop(): File?

    /** Останавливает запись и удаляет файл. */
    fun discard()
}
