package ru.itmo.talkmate.ui

import android.os.Bundle
import android.view.View
import ru.itmo.talkmate.R
import ru.itmo.talkmate.data.Stats
import ru.itmo.talkmate.databinding.ActivityStatsBinding

class StatsActivity : BaseActivity() {
    private lateinit var binding: ActivityStatsBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityStatsBinding.inflate(layoutInflater)
        setContentView(binding.root)
        load()
    }

    override fun onRetry() = load()

    private fun load() {
        call(progress = binding.progress, request = { it.stats() }) { show(it) }
        // Индикатор в этом экране стоит в потоке вёрстки, поэтому после загрузки убираем его совсем.
    }

    private fun show(stats: Stats) {
        binding.progress.visibility = View.GONE
        val points = stats.points
        if (points.isEmpty()) {
            binding.tvEmpty.visibility = View.VISIBLE
            return
        }
        val dates = points.map { Formatters.shortDate(it.date) }
        val t = stats.thresholds

        fun num(key: String, decimals: Int = 0): String =
            t[key]?.let { if (decimals == 0) Math.round(it).toString() else "%.${decimals}f".format(it) } ?: "?"

        // Карточки чередуют розовый и синий фон, как в макете.
        binding.chartRate.show(
            getString(R.string.chart_rate), points.map { it.speechRate.toFloat() }, dates,
            zone = range(t["rate_slow"], t["rate_fast"]), blue = false,
            note = getString(R.string.note_range, num("rate_slow"), num("rate_fast")),
        )
        binding.chartFillers.show(
            getString(R.string.chart_fillers), points.map { it.numFillers.toFloat() }, dates,
            zone = range(0.0, t["fillers_max"]), blue = true,
            note = getString(R.string.note_max, num("fillers_max")),
        )
        binding.chartVolume.show(
            getString(R.string.chart_volume), points.map { it.volumeDb.toFloat() }, dates,
            zone = range(t["volume_quiet_db"], t["volume_loud_db"]), blue = false, decimals = 1,
            note = getString(R.string.note_range, num("volume_quiet_db"), num("volume_loud_db")),
        )
        binding.chartPitch.show(
            getString(R.string.chart_pitch), points.map { it.pitchVariability.toFloat() }, dates,
            zone = t["monotony_min_semitones"]?.let { it.toFloat() to Float.MAX_VALUE }, blue = true, decimals = 1,
            note = getString(R.string.note_pitch, num("monotony_min_semitones")),
        )
        // Чёткость есть только у записей, сделанных после появления этой оценки.
        val withClarity = points.filter { it.clarity != null }
        if (withClarity.isNotEmpty()) {
            binding.chartClarity.show(
                getString(R.string.chart_clarity), withClarity.map { it.clarity!!.toFloat() }, withClarity.map { Formatters.shortDate(it.date) },
                zone = t["clarity_unclear"]?.let { it.toFloat() to Float.MAX_VALUE }, blue = false,
                note = getString(R.string.note_clarity, num("clarity_unclear")),
            )
        }
    }

    private fun range(low: Double?, high: Double?): Pair<Float, Float>? =
        if (low == null || high == null) null else low.toFloat() to high.toFloat()
}
