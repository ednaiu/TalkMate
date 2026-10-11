package ru.itmo.talkmate.audio

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import java.io.File
import java.io.RandomAccessFile
import kotlin.concurrent.thread

/** Пишет звук с микрофона в WAV 16 кГц моно. Такой файл сервер разбирает без перекодирования. */
class WavRecorder : Recorder {
    @Volatile
    override var state = Recorder.State.IDLE
        private set

    @Volatile
    private var pcmBytes = 0L
    private var audioRecord: AudioRecord? = null
    private var worker: Thread? = null
    private var file: File? = null

    override val elapsedMs: Long get() = WavFormat.durationMs(pcmBytes)

    @SuppressLint("MissingPermission") // разрешение проверяет экран записи перед вызовом
    override fun start(output: File) {
        check(state == Recorder.State.IDLE) { "Запись уже идёт" }
        val minBuffer = AudioRecord.getMinBufferSize(
            WavFormat.SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT,
        )
        check(minBuffer > 0) { "Микрофон не поддерживает нужный формат" }
        val bufferSize = maxOf(minBuffer, WavFormat.SAMPLE_RATE) // запас на полсекунды
        val record = AudioRecord(
            MediaRecorder.AudioSource.MIC, WavFormat.SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, bufferSize,
        )
        if (record.state != AudioRecord.STATE_INITIALIZED) {
            record.release()
            error("Не удалось включить микрофон")
        }
        record.startRecording()
        audioRecord = record
        file = output
        pcmBytes = 0
        state = Recorder.State.RECORDING

        worker = thread(name = "wav-recorder") {
            // Читаем по 20 мс звука: счётчик записанного времени тогда идёт плавно, а не скачками по четверти секунды.
            val buffer = ByteArray(WavFormat.SAMPLE_RATE * 2 / 50)
            RandomAccessFile(output, "rw").use { raf ->
                raf.setLength(0)
                raf.write(WavFormat.header(0))
                while (state == Recorder.State.RECORDING || state == Recorder.State.PAUSED) {
                    val read = record.read(buffer, 0, buffer.size)
                    if (read <= 0) {
                        // На паузе AudioRecord остановлен и чтение сразу возвращает 0.
                        Thread.sleep(20)
                        continue
                    }
                    if (state == Recorder.State.RECORDING) {
                        raf.write(buffer, 0, read)
                        pcmBytes += read
                    }
                }
                raf.seek(0)
                raf.write(WavFormat.header(pcmBytes))
            }
        }
    }

    override fun pause() {
        if (state != Recorder.State.RECORDING) return
        state = Recorder.State.PAUSED
        runCatching { audioRecord?.stop() }
    }

    override fun resume() {
        if (state != Recorder.State.PAUSED) return
        runCatching { audioRecord?.startRecording() }
        state = Recorder.State.RECORDING
    }

    override fun stop(): File? {
        if (state != Recorder.State.RECORDING && state != Recorder.State.PAUSED) return file
        state = Recorder.State.STOPPED
        runCatching { audioRecord?.stop() }
        worker?.join(2000)
        audioRecord?.release()
        audioRecord = null
        worker = null
        return file
    }

    override fun discard() {
        stop()
        file?.delete()
        file = null
        pcmBytes = 0
        state = Recorder.State.IDLE
    }
}
