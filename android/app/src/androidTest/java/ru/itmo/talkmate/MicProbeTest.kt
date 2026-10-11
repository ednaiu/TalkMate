package ru.itmo.talkmate

import android.Manifest
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.rule.GrantPermissionRule
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import ru.itmo.talkmate.audio.WavRecorder
import java.io.File

/**
 * Диагностика микрофона устройства или эмулятора: пишет звук диктофоном приложения в файл, который можно забрать и послушать.
 * Обычный прогон тест пропускает. Запуск:
 * adb shell am instrument -w -e class ru.itmo.talkmate.MicProbeTest -e micProbeSeconds 10 \
 *     ru.itmo.talkmate.test/androidx.test.runner.AndroidJUnitRunner
 * adb pull /sdcard/Android/data/ru.itmo.talkmate/files/mic_probe.wav
 */
@RunWith(AndroidJUnit4::class)
class MicProbeTest {
    @get:Rule
    val microphone: GrantPermissionRule = GrantPermissionRule.grant(Manifest.permission.RECORD_AUDIO)

    @Test
    fun recordProbe() {
        val seconds = InstrumentationRegistry.getArguments().getString("micProbeSeconds")?.toLongOrNull()
        assumeTrue("micProbeSeconds не задан", seconds != null)
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val file = File(context.getExternalFilesDir(null), "mic_probe.wav")
        val recorder = WavRecorder()
        recorder.start(file)
        Thread.sleep(seconds!! * 1000)
        recorder.stop()
    }
}
