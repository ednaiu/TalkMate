package ru.itmo.talkmate.ui

import android.content.Context
import android.graphics.Canvas
import android.graphics.DashPathEffect
import android.graphics.Paint
import android.graphics.Path
import android.util.AttributeSet
import android.view.View
import androidx.core.content.ContextCompat
import ru.itmo.talkmate.R

/** Маленький график темпа в личном кабинете: точки последних тренировок на фоне полосы нормы. */
class TempoChartView @JvmOverloads constructor(context: Context, attrs: AttributeSet? = null) : View(context, attrs) {
    private var values: List<Int> = emptyList()
    private var labels: List<String> = emptyList()
    private var slow = 0f
    private var fast = 0f
    private val density = resources.displayMetrics.density

    private val band = Paint().apply { color = ContextCompat.getColor(context, R.color.pink) }
    private val line = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = ContextCompat.getColor(context, R.color.blue)
        style = Paint.Style.STROKE
        strokeWidth = 2.5f * density
        strokeCap = Paint.Cap.ROUND
    }
    private val dot = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = ContextCompat.getColor(context, R.color.blue) }
    private val grid = Paint().apply {
        color = 0xFFDDDEE6.toInt()
        style = Paint.Style.STROKE
        strokeWidth = density
        pathEffect = DashPathEffect(floatArrayOf(4 * density, 4 * density), 0f)
    }
    private val text = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = ContextCompat.getColor(context, R.color.grey_text)
        textSize = 12 * resources.displayMetrics.scaledDensity
        textAlign = Paint.Align.CENTER
    }

    fun show(values: List<Int>, labels: List<String>, slow: Double, fast: Double) {
        this.values = values
        this.labels = labels
        this.slow = slow.toFloat()
        this.fast = fast.toFloat()
        contentDescription = values.joinToString(", ")
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        if (values.isEmpty()) return
        val side = 18 * density
        val top = 6 * density
        val bottom = height - 22 * density
        val low = minOf(values.min().toFloat(), slow) - 8
        val high = maxOf(values.max().toFloat(), fast) + 8
        fun y(value: Float) = bottom - (value - low) / (high - low) * (bottom - top)
        fun x(index: Int) = if (values.size == 1) width / 2f else side + index * (width - 2 * side) / (values.size - 1)

        canvas.drawRect(side, y(fast), width - side, y(slow), band)
        for (index in values.indices) {
            canvas.drawLine(x(index), top, x(index), bottom, grid)
            canvas.drawText(labels.getOrElse(index) { "" }, x(index), height - 5 * density, text)
        }
        val path = Path()
        values.forEachIndexed { index, value ->
            if (index == 0) path.moveTo(x(index), y(value.toFloat())) else path.lineTo(x(index), y(value.toFloat()))
        }
        canvas.drawPath(path, line)
        values.forEachIndexed { index, value -> canvas.drawCircle(x(index), y(value.toFloat()), 4.5f * density, dot) }
    }
}
