package ru.itmo.talkmate.ui

import android.content.Context
import android.content.Intent
import android.graphics.Typeface
import android.os.Bundle
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.style.BackgroundColorSpan
import android.text.style.ForegroundColorSpan
import android.text.style.RelativeSizeSpan
import android.text.style.StyleSpan
import android.text.style.UnderlineSpan
import android.view.View
import androidx.core.content.ContextCompat
import androidx.core.content.IntentCompat
import ru.itmo.talkmate.Lang
import ru.itmo.talkmate.R
import ru.itmo.talkmate.data.SpeechResult
import ru.itmo.talkmate.databinding.ActivityResultsBinding

class ResultsActivity : BaseActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val result = IntentCompat.getSerializableExtra(intent, EXTRA_RESULT, SpeechResult::class.java)
        if (result == null) {
            finish()
            return
        }
        val binding = ActivityResultsBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val feedback = result.feedback
        binding.tvRate.text = Formatters.rate(feedback.speechRate)
        binding.tvVolume.text = Formatters.volume(feedback.volume)
        binding.tvMonotony.text = Formatters.monotonyDescription(feedback.monotony)
        binding.tvEmotion.text = Formatters.emotion(feedback.emotion)
        binding.tvClarity.text = Formatters.clarity(feedback.clarity, feedback.clarityLevel)
        binding.tvFillers.text = Formatters.fillers(feedback.numFillers)
        if (feedback.fillers.isNotEmpty()) {
            binding.tvFillerWords.text = getString(R.string.fillers_found, feedback.fillers.joinToString(", ") { Lang.t("«$it»", "“$it”") })
            binding.tvFillerWords.visibility = View.VISIBLE
        }
        // Содержание: о чём выступление и как оно построено. Сервер старой версии этих данных не присылает.
        result.content?.let { content ->
            binding.cardContent.visibility = View.VISIBLE
            binding.tvMainIdea.text = content.mainIdea ?: getString(R.string.main_idea_missing)
            if (content.keywords.isNotEmpty()) {
                binding.tvKeywords.text = getString(R.string.keywords, content.keywords.joinToString(", "))
                binding.tvKeywords.visibility = View.VISIBLE
            }
            binding.tvStructure.text = Formatters.structure(content.structureLevel)
            binding.tvStructureSummary.text = content.structureSummary
        }
        // Презентация: насколько слова совпали со слайдами. Блок есть, только если к записи приложили PDF.
        result.slides?.let { report ->
            binding.cardSlides.visibility = View.VISIBLE
            if (report.error != null) {
                binding.tvSlidesSummary.text = report.error
                binding.tvSlidesNotes.visibility = View.GONE
                return@let
            }
            binding.tvSlidesSummary.text = getString(R.string.slides_summary, report.pages,
                report.coverage?.let { "$it%" } ?: "0%", report.reading) + "\n" +
                getString(if (report.timed) R.string.slides_timed else R.string.slides_guessed)
            binding.tvSlidesNotes.text = Markup.render(report.notes.joinToString("\n\n"), ContextCompat.getColor(this, R.color.ink))
            val gap = (10 * resources.displayMetrics.density).toInt()
            for (item in report.items) {
                val lines = mutableListOf(
                    Lang.t("**Слайд ${item.page}.**", "**Slide ${item.page}.**") + " ${item.title}".trimEnd(),
                    Formatters.slideLine(item.seconds, item.status, item.coverage, item.reading, item.dense, item.smallText),
                )
                if (item.missed.isNotEmpty()) lines += getString(R.string.slides_missed, item.missed.joinToString(", "))
                binding.slidesList.addView(android.widget.TextView(this).apply {
                    text = Markup.render(lines.joinToString("\n"), ContextCompat.getColor(this@ResultsActivity, R.color.ink))
                    textSize = 15f
                    setTextColor(ContextCompat.getColor(this@ResultsActivity, R.color.grey_title))
                    setLineSpacing(0f, 1.15f)
                    setPadding(0, gap, 0, 0)
                })
            }
        }
        binding.tvRecTitle.text = result.recommendationTitle
        binding.tvRecText.text = Markup.render(result.recommendationText, ContextCompat.getColor(this, R.color.ink))
        // Расшифровка: текст, который сервер распознал в записи. По нему видно, откуда взялись темп и заполнители.
        binding.tvTranscript.text = transcript(result)
        binding.tvTranscriptLegend.text = if (result.segments.isEmpty()) "" else
            getString(R.string.transcript_legend) + "\n" + TranscriptMarks.summary(result.segments)
        binding.btnTranscript.visibility = if (result.text.isBlank()) View.GONE else View.VISIBLE
        var transcriptShown = savedInstanceState?.getBoolean(KEY_TRANSCRIPT) ?: false
        fun renderTranscript() {
            binding.tvTranscript.visibility = if (transcriptShown) View.VISIBLE else View.GONE
            binding.tvTranscriptLegend.visibility = if (transcriptShown && result.segments.isNotEmpty()) View.VISIBLE else View.GONE
            binding.btnTranscript.setText(if (transcriptShown) R.string.transcript_hide else R.string.transcript_show)
        }
        renderTranscript()
        binding.btnTranscript.setOnClickListener {
            transcriptShown = !transcriptShown
            renderTranscript()
        }
        transcriptState = { transcriptShown }
        binding.btnAgain.setOnClickListener {
            startActivity(Intent(this, RecordActivity::class.java))
            finish()
        }
    }

    private var transcriptState: () -> Boolean = { false }

    /** Расшифровка с разметкой: над фразой пометки о темпе и окраске, заполнители выделены цветом. */
    private fun transcript(result: SpeechResult): CharSequence {
        if (result.segments.isEmpty()) return result.text   // сервер старой версии: показываем текст как есть
        val builder = SpannableStringBuilder()
        val fillerColor = ContextCompat.getColor(this, R.color.error)
        val fillerBackground = ContextCompat.getColor(this, R.color.pink_card)
        for (segment in result.segments) {
            if (builder.isNotEmpty()) builder.append("\n\n")
            for ((index, mark) in TranscriptMarks.marks(segment).withIndex()) {
                val start = builder.length
                builder.append(if (index == 0) "" else "  ·  ").append(mark.text)
                val color = when (mark.kind) {
                    TranscriptMarks.Kind.TEMPO -> R.color.blue_dark
                    TranscriptMarks.Kind.NEGATIVE_EMOTION -> R.color.error
                    TranscriptMarks.Kind.EMOTION -> R.color.grey_text
                }
                builder.setSpan(ForegroundColorSpan(ContextCompat.getColor(this, color)), start, builder.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                builder.setSpan(StyleSpan(Typeface.BOLD), start, builder.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                builder.setSpan(RelativeSizeSpan(0.82f), start, builder.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            }
            if (TranscriptMarks.marks(segment).isNotEmpty()) builder.append("\n")
            for (part in segment.parts) {
                val start = builder.length
                builder.append(part.text)
                if (part.filler) {
                    builder.setSpan(ForegroundColorSpan(fillerColor), start, builder.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                    builder.setSpan(BackgroundColorSpan(fillerBackground), start, builder.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                    builder.setSpan(StyleSpan(Typeface.BOLD), start, builder.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                } else if (part.unclear) {
                    // Неразборчивое слово: подчёркнуто и набрано курсивом.
                    builder.setSpan(UnderlineSpan(), start, builder.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                    builder.setSpan(StyleSpan(Typeface.ITALIC), start, builder.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                }
            }
        }
        return builder
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        outState.putBoolean(KEY_TRANSCRIPT, transcriptState())
    }

    companion object {
        private const val EXTRA_RESULT = "result"
        private const val KEY_TRANSCRIPT = "transcript_shown"

        fun intent(context: Context, result: SpeechResult): Intent =
            Intent(context, ResultsActivity::class.java).putExtra(EXTRA_RESULT, result)
    }
}
