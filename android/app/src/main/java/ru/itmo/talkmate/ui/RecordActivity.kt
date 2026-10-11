package ru.itmo.talkmate.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.pdf.PdfRenderer
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.ParcelFileDescriptor
import android.provider.OpenableColumns
import android.view.View
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import ru.itmo.talkmate.R
import ru.itmo.talkmate.ServiceLocator
import ru.itmo.talkmate.audio.Recorder
import ru.itmo.talkmate.audio.Recorder.State
import ru.itmo.talkmate.data.SlideMark
import ru.itmo.talkmate.databinding.ActivityRecordBinding
import java.io.File

class RecordActivity : BaseActivity() {
    private lateinit var binding: ActivityRecordBinding
    private lateinit var recorder: Recorder
    private val handler = Handler(Looper.getMainLooper())
    private var analyzing = false
    private var recording: File? = null
    private var handedOver = false
    private var slides: File? = null
    private var slidesName: String? = null
    private var renderer: PdfRenderer? = null
    private var page = 0
    private val marks = mutableListOf<SlideMark>()

    private val tick = object : Runnable {
        override fun run() {
            binding.tvTimer.text = Formatters.timer(recorder.elapsedMs)
            if (recorder.state == State.RECORDING) handler.postDelayed(this, TICK_MS)
        }
    }

    private val askMicrophone = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) startRecording() else binding.tvHint.setText(R.string.hint_no_permission)
    }

    private val pickSlides = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) attachSlides(uri)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityRecordBinding.inflate(layoutInflater)
        setContentView(binding.root)
        savedInstanceState?.getString(KEY_SLIDES)?.let { name ->
            val saved = File(cacheDir, SLIDES_FILE)
            if (saved.exists()) {
                slides = saved
                slidesName = name
                openSlides(saved)
            }
        }
        // Экран можно открыть сразу с презентацией: так его запускают из других мест приложения и из тестов.
        if (slides == null) {
            intent.getStringExtra(EXTRA_SLIDES)?.let(::File)?.takeIf { it.exists() }?.let { file ->
                slides = file
                slidesName = file.name
                openSlides(file)
            }
        }
        binding.btnAttachSlides.setOnClickListener { pickSlides.launch(arrayOf("application/pdf")) }
        binding.btnRemoveSlides.setOnClickListener {
            slides = null
            slidesName = null
            closeSlides()
            marks.clear()
            render()
        }
        binding.btnPrevSlide.setOnClickListener { flip(-1) }
        binding.btnNextSlide.setOnClickListener { flip(1) }
        recorder = ServiceLocator.recorderFactory()

        binding.btnRecordPause.setOnClickListener {
            when (recorder.state) {
                State.RECORDING -> {
                    recorder.pause()
                    render()
                }
                State.PAUSED -> {
                    recorder.resume()
                    handler.post(tick)
                    render()
                }
                // Экран перерисует сам startRecording: после неудачи на нём остаётся пояснение.
                State.IDLE, State.STOPPED -> ensurePermissionAndStart()
            }
        }
        binding.btnStop.setOnClickListener {
            recording = recorder.stop()
            render()
        }
        binding.btnAnalyze.setOnClickListener { analyze() }
        render()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        outState.putString(KEY_SLIDES, slidesName)
    }

    /** Копирует выбранный PDF к себе: доступ к файлу по ссылке системы пропадает вместе с экраном выбора. */
    private fun attachSlides(uri: Uri) {
        val target = File(cacheDir, SLIDES_FILE)
        try {
            contentResolver.openInputStream(uri)!!.use { input -> target.outputStream().use { input.copyTo(it) } }
        } catch (e: Exception) {
            binding.tvHint.setText(R.string.slides_failed)
            return
        }
        if (target.length() > MAX_SLIDES_BYTES) {
            target.delete()
            binding.tvHint.setText(R.string.slides_too_big)
            return
        }
        slidesName = contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) cursor.getString(0) else null
        } ?: "PDF"
        slides = target
        openSlides(target)
        // Презентацию приложили посреди записи: с этого момента на экране её первый слайд.
        marks.clear()
        if (recorder.state == State.RECORDING || recorder.state == State.PAUSED) markSlide()
        render()
    }

    /** Открывает PDF для показа. Если телефон не смог его прочитать, файл всё равно уйдёт на сервер, но без листания. */
    private fun openSlides(file: File) {
        closeSlides()
        page = 0
        try {
            renderer = PdfRenderer(ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY))
            showSlide()
        } catch (e: Exception) {
            renderer = null
        }
    }

    private fun closeSlides() {
        try {
            renderer?.close()
        } catch (e: Exception) {
            // уже закрыт
        }
        renderer = null
        binding.ivSlide.setImageDrawable(null)
    }

    private fun showSlide() {
        val pdf = renderer ?: return
        pdf.openPage(page).use { sheet ->
            val width = SLIDE_WIDTH_PX
            val bitmap = Bitmap.createBitmap(width, (width.toFloat() * sheet.height / sheet.width).toInt().coerceAtLeast(1), Bitmap.Config.ARGB_8888)
            bitmap.eraseColor(Color.WHITE)
            sheet.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
            binding.ivSlide.setImageBitmap(bitmap)
        }
        binding.tvSlideNumber.text = getString(R.string.slide_number, page + 1, pdf.pageCount)
        binding.btnPrevSlide.isEnabled = page > 0
        binding.btnNextSlide.isEnabled = page < pdf.pageCount - 1
    }

    /** Листает слайды. Во время записи переключение запоминается со временем: по нему сервер считает время на слайд. */
    private fun flip(step: Int) {
        val pdf = renderer ?: return
        val target = (page + step).coerceIn(0, pdf.pageCount - 1)
        if (target == page) return
        page = target
        showSlide()
        if (recorder.state == State.RECORDING || recorder.state == State.PAUSED) markSlide()
    }

    private fun markSlide() {
        marks += SlideMark(page + 1, recorder.elapsedMs / 1000.0)
    }

    private fun ensurePermissionAndStart() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            startRecording()
        } else {
            askMicrophone.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    private fun startRecording() {
        recorder.discard()
        recording = null
        try {
            recorder.start(File(cacheDir, "speech.wav"))
        } catch (e: Exception) {
            recorder.discard()
            render()
            binding.tvHint.setText(R.string.hint_mic_failed)
            return
        }
        // Новая запись: отметки начинаются с того слайда, который сейчас на экране.
        marks.clear()
        if (renderer != null) markSlide()
        handler.post(tick)
        render()
    }

    private fun analyze() {
        if (recorder.state == State.RECORDING || recorder.state == State.PAUSED) recording = recorder.stop()
        val file = recording
        if (file == null || recorder.elapsedMs < MIN_RECORDING_MS) {
            recorder.discard()
            recording = null
            render()
            binding.tvHint.setText(R.string.hint_too_short)
            return
        }
        analyzing = true
        render()
        call(
            progress = binding.progress,
            onError = {
                analyzing = false
                render()
                showErrorScreen(it)
            },
            request = { it.uploadSpeech(file, slides, marks.toList().takeIf { slides != null }) },
        ) { result ->
            handedOver = true
            recorder.discard()
            startActivity(ResultsActivity.intent(this, result))
            finish()
        }
    }

    /** Экран ошибки закрыли: запись сохранена, анализ можно повторить. */
    override fun onErrorDismissed() = Unit

    override fun onRetry() = analyze()

    private fun render() {
        val state = recorder.state
        val active = state == State.RECORDING || state == State.PAUSED
        binding.tvTimer.text = Formatters.timer(recorder.elapsedMs)
        binding.btnRecordPause.isEnabled = !analyzing
        binding.btnStop.isEnabled = active && !analyzing
        binding.btnAnalyze.isEnabled = (active || state == State.STOPPED) && !analyzing
        binding.btnAttachSlides.visibility = if (slides == null) View.VISIBLE else View.GONE
        binding.slidesAttached.visibility = if (slides == null) View.GONE else View.VISIBLE
        binding.slideViewer.visibility = if (renderer == null) View.GONE else View.VISIBLE
        binding.tvSlidesName.text = getString(R.string.slides_attached, slidesName.orEmpty())
        binding.btnAttachSlides.isEnabled = !analyzing
        binding.btnRemoveSlides.isEnabled = !analyzing
        val (icon, description) = when (state) {
            State.RECORDING -> R.drawable.ic_pause to R.string.record_pause
            State.PAUSED -> R.drawable.ic_play to R.string.record_resume
            State.IDLE, State.STOPPED -> R.drawable.ic_record to R.string.record_start
        }
        binding.btnRecordPause.setImageResource(icon)
        binding.btnRecordPause.contentDescription = getString(description)
        binding.tvHint.setText(
            when {
                analyzing -> R.string.hint_analyzing
                state == State.RECORDING -> R.string.hint_recording
                state == State.PAUSED -> R.string.hint_paused
                state == State.STOPPED -> R.string.hint_stopped
                else -> R.string.hint_idle
            },
        )
    }

    override fun onStop() {
        super.onStop()
        // Экран ушёл с глаз: запись ставим на паузу, чтобы не писать микрофон в фоне.
        if (recorder.state == State.RECORDING) {
            recorder.pause()
            render()
        }
    }

    override fun onDestroy() {
        handler.removeCallbacks(tick)
        closeSlides()
        if (!handedOver) recorder.discard()
        super.onDestroy()
    }

    companion object {
        const val EXTRA_SLIDES = "slides"
        private const val TICK_MS = 33L   // таймер показывает миллисекунды и обновляется каждый кадр
        private const val MIN_RECORDING_MS = 3000L
        private const val MAX_SLIDES_BYTES = 40L * 1024 * 1024
        private const val SLIDES_FILE = "slides.pdf"
        private const val SLIDE_WIDTH_PX = 1080
        private const val KEY_SLIDES = "slides_name"
    }
}
