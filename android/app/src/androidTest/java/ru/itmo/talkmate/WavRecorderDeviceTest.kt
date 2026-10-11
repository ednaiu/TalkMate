package ru.itmo.talkmate

import android.Manifest
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.rule.GrantPermissionRule
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import ru.itmo.talkmate.audio.Recorder
import ru.itmo.talkmate.audio.WavFormat
import ru.itmo.talkmate.audio.WavRecorder
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** Проверка настоящего диктофона на устройстве: файл WAV, пауза, удаление. */
@RunWith(AndroidJUnit4::class)
class WavRecorderDeviceTest {
    @get:Rule
    val microphone: GrantPermissionRule = GrantPermissionRule.grant(Manifest.permission.RECORD_AUDIO)

    private val file = File(InstrumentationRegistry.getInstrumentation().targetContext.cacheDir, "recorder_test.wav")

    @Test
    fun recordsValidWavAndHonoursPause() {
        val recorder = WavRecorder()
        recorder.start(file)
        assertEquals(Recorder.State.RECORDING, recorder.state)
        Thread.sleep(1500)

        recorder.pause()
        Thread.sleep(300) // даём потоку записи дописать последний буфер
        val atPause = recorder.elapsedMs
        Thread.sleep(1200)
        assertEquals("во время паузы запись не растёт", atPause, recorder.elapsedMs)

        recorder.resume()
        Thread.sleep(1000)
        val result = recorder.stop()
        assertEquals(Recorder.State.STOPPED, recorder.state)
        assertEquals(file, result)

        val elapsed = recorder.elapsedMs
        assertTrue("записано $elapsed мс", elapsed in 1800..3200)

        val bytes = file.readBytes()
        val header = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        val pcmBytes = bytes.size - WavFormat.HEADER_SIZE
        assertEquals("RIFF", String(bytes, 0, 4))
        assertEquals("WAVE", String(bytes, 8, 4))
        assertEquals(16_000, header.getInt(24))
        assertEquals(pcmBytes, header.getInt(40))
        assertEquals(bytes.size - 8, header.getInt(4))
        assertEquals(elapsed, WavFormat.durationMs(pcmBytes.toLong()))

        recorder.discard()
        assertFalse(file.exists())
        assertEquals(Recorder.State.IDLE, recorder.state)
        assertEquals(0, recorder.elapsedMs)
    }
}
