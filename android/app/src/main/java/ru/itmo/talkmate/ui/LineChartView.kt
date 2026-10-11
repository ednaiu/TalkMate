package ru.itmo.talkmate.ui

import android.content.Context
import android.graphics.Canvas
import android.graphics.DashPathEffect
import android.graphics.Paint
import android.graphics.Path
import android.text.StaticLayout
import android.text.TextPaint
import android.util.AttributeSet
import android.view.View
import androidx.core.content.ContextCompat
import ru.itmo.talkmate.R
import kotlin.math.max
import kotlin.math.min

/** График показателя по записям: оси со стрелками из макета, линия значений и полоса нормы. */
class LineChartView @JvmOverloads constructor(context: Context, attrs: AttributeSet? = null) : View(context, attrs) {
    private val density = resources.displayMetrics.density
    private val scaled = resources.displayMetrics.scaledDensity

    private var title = ""
    private var values: List<Float> = emptyList()
    private var dates: List<String> = emptyList()
    private var zone: Pair<Float, Float>? = null
    private var decimals = 0
    private var note = ""

    private val axisPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = 1.5f * density
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }
    private val linePaint = Paint(axisPaint).apply { strokeWidth = 2.5f * density }
    private val dotPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val zonePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = 1.2f * density
        pathEffect = DashPathEffect(floatArrayOf(6 * density, 5 * density), 0f)
    }
    private val notePaint = TextPaint(Paint.ANTI_ALIAS_FLAG).apply { textSize = 13 * scaled }
    private var noteLayout: StaticLayout? = null
    private val titlePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { textSize = 17 * scaled }
    private val labelPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { textSize = 14 * scaled }

    fun show(
        title: String,
        values: List<Float>,
        dates: List<String>,
        zone: Pair<Float, Float>?,
        blue: Boolean,
        decimals: Int = 0,
        note: String = "",
    ) {
        this.note = note
        noteLayout = null
        this.title = title
        this.values = values
        this.dates = dates
        this.zone = zone
        this.decimals = decimals

        setBackgroundResource(if (blue) R.drawable.bg_chart_blue else R.drawable.bg_chart_pink)
        val axisColor = ContextCompat.getColor(context, if (blue) R.color.pink else R.color.blue)
        val textColor = ContextCompat.getColor(context, if (blue) R.color.white else R.color.grey_title)
        axisPaint.color = axisColor
        linePaint.color = ContextCompat.getColor(context, if (blue) R.color.white else R.color.blue)
        dotPaint.color = linePaint.color
        zonePaint.color = ContextCompat.getColor(context, if (blue) R.color.white else R.color.blue_dark)
        zonePaint.alpha = 170
        notePaint.color = textColor
        notePaint.alpha = 215
        titlePaint.color = textColor
        labelPaint.color = textColor

        contentDescription = "$title: " + values.joinToString(", ") { format(it) }
        requestLayout()
        visibility = VISIBLE
        invalidate()
    }

    private fun format(value: Float) = if (decimals == 0) Math.round(value).toString() else "%.${decimals}f".format(value)

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (values.isEmpty()) return
        val left = 30 * density
        val right = width - 26 * density
        // Пояснение о норме занимает одну или две строки, график начинается под ним.
        val noteWidth = (width - 56 * density).toInt().coerceAtLeast(1)
        val layout = noteLayout ?: StaticLayout.Builder.obtain(note, 0, note.length, notePaint, noteWidth).build().also { noteLayout = it }
        val noteTop = 60 * density
        val top = noteTop + layout.height + 22 * density
        val bottom = height - 40 * density
        val arrow = 6 * density

        // Заголовок и последнее значение стоят на разных строках: длинный заголовок иначе наезжает на число.
        canvas.drawText(title, left, 30 * density, titlePaint)
        canvas.drawText(context.getString(R.string.chart_last, format(values.last())), left, 52 * density, labelPaint)
        canvas.save()
        canvas.translate(left, noteTop)
        layout.draw(canvas)
        canvas.restore()

        // Диапазон по вертикали: значения и граница нормы с запасом в десятую часть.
        var low = values.min()
        var high = values.max()
        zone?.let { (zoneLow, zoneHigh) ->
            low = min(low, zoneLow)
            if (zoneHigh != Float.MAX_VALUE) high = max(high, zoneHigh)
        }
        val pad = max((high - low) * 0.1f, 0.5f)
        low -= pad
        high += pad
        val plotLeft = left + 8 * density
        val plotRight = right - 14 * density
        val plotTop = top + 8 * density
        fun y(value: Float) = bottom - (value - low) / (high - low) * (bottom - plotTop)
        fun x(index: Int) = if (values.size == 1) (plotLeft + plotRight) / 2 else plotLeft + index * (plotRight - plotLeft) / (values.size - 1)

        // Границы нормы: пунктирные линии. Нулевая граница не рисуется: у счётчика заполнителей норма «от нуля»,
        // и линия у самой оси читалась бы как порог.
        zone?.let { (zoneLow, zoneHigh) ->
            for (bound in listOf(zoneLow, zoneHigh)) {
                if (bound == Float.MAX_VALUE || bound == 0f) continue
                val line = y(bound)
                if (line > plotTop - 1 && line < bottom - 2 * density) canvas.drawLine(left, line, plotRight, line, zonePaint)
            }
        }

        // Оси со стрелками.
        val axes = Path().apply {
            moveTo(left, top - 8 * density)
            lineTo(left, bottom)
            lineTo(right, bottom)
            moveTo(left - arrow, top - 8 * density + arrow)
            lineTo(left, top - 8 * density)
            lineTo(left + arrow, top - 8 * density + arrow)
            moveTo(right - arrow, bottom - arrow)
            lineTo(right, bottom)
            lineTo(right - arrow, bottom + arrow)
        }
        canvas.drawPath(axes, axisPaint)

        val line = Path()
        values.forEachIndexed { index, value ->
            if (index == 0) line.moveTo(x(index), y(value)) else line.lineTo(x(index), y(value))
        }
        canvas.drawPath(line, linePaint)
        values.forEachIndexed { index, value -> canvas.drawCircle(x(index), y(value), 3.5f * density, dotPaint) }

        if (dates.isNotEmpty()) {
            val baseline = bottom + 22 * density
            canvas.drawText(dates.first(), left, baseline, labelPaint)
            if (dates.size > 1) {
                canvas.drawText(dates.last(), plotRight - labelPaint.measureText(dates.last()), baseline, labelPaint)
            }
        }
    }
}
