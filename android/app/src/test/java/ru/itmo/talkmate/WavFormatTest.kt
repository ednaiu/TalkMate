package ru.itmo.talkmate

import org.junit.Assert.assertEquals
import org.junit.Test
import ru.itmo.talkmate.audio.WavFormat
import java.nio.ByteBuffer
import java.nio.ByteOrder

class WavFormatTest {
    @Test
    fun headerDescribesMono16kPcm() {
        val pcmBytes = 32_000L // одна секунда
        val header = WavFormat.header(pcmBytes)
        val buffer = ByteBuffer.wrap(header).order(ByteOrder.LITTLE_ENDIAN)
        assertEquals(44, header.size)
        assertEquals("RIFF", String(header, 0, 4))
        assertEquals(pcmBytes.toInt() + 36, buffer.getInt(4))
        assertEquals("WAVE", String(header, 8, 4))
        assertEquals("fmt ", String(header, 12, 4))
        assertEquals(16, buffer.getInt(16))
        assertEquals(1, buffer.getShort(20).toInt())      // PCM
        assertEquals(1, buffer.getShort(22).toInt())      // моно
        assertEquals(16_000, buffer.getInt(24))
        assertEquals(32_000, buffer.getInt(28))           // байт в секунду
        assertEquals(2, buffer.getShort(32).toInt())
        assertEquals(16, buffer.getShort(34).toInt())
        assertEquals("data", String(header, 36, 4))
        assertEquals(pcmBytes.toInt(), buffer.getInt(40))
    }

    @Test
    fun duration() {
        assertEquals(0, WavFormat.durationMs(0))
        assertEquals(1000, WavFormat.durationMs(32_000))
        assertEquals(140_000, WavFormat.durationMs(32_000L * 140))
    }
}
