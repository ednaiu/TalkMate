package ru.itmo.talkmate.audio

import java.nio.ByteBuffer
import java.nio.ByteOrder

/** Заголовок WAV для несжатого звука PCM 16 бит. */
object WavFormat {
    const val SAMPLE_RATE = 16_000
    const val HEADER_SIZE = 44

    fun header(pcmBytes: Long, sampleRate: Int = SAMPLE_RATE, channels: Int = 1): ByteArray {
        val bytesPerFrame = channels * 2
        return ByteBuffer.allocate(HEADER_SIZE).order(ByteOrder.LITTLE_ENDIAN).apply {
            put("RIFF".toByteArray(Charsets.US_ASCII))
            putInt((pcmBytes + HEADER_SIZE - 8).toInt())
            put("WAVE".toByteArray(Charsets.US_ASCII))
            put("fmt ".toByteArray(Charsets.US_ASCII))
            putInt(16)
            putShort(1)
            putShort(channels.toShort())
            putInt(sampleRate)
            putInt(sampleRate * bytesPerFrame)
            putShort(bytesPerFrame.toShort())
            putShort(16)
            put("data".toByteArray(Charsets.US_ASCII))
            putInt(pcmBytes.toInt())
        }.array()
    }

    fun durationMs(pcmBytes: Long, sampleRate: Int = SAMPLE_RATE, channels: Int = 1): Long =
        pcmBytes * 1000 / (sampleRate.toLong() * channels * 2)
}
