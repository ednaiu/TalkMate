package ru.itmo.talkmate.ui

import android.content.Context
import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import ru.itmo.talkmate.R
import ru.itmo.talkmate.databinding.ActivityErrorBinding

/** Экран «Ooops…». Назад возвращает RESULT_CANCELED, кнопка повтора возвращает RESULT_OK. */
class ErrorActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val binding = ActivityErrorBinding.inflate(layoutInflater)
        setContentView(binding.root)
        binding.tvErrorMessage.text = intent.getStringExtra(EXTRA_MESSAGE)?.takeIf { it.isNotBlank() }
            ?: getString(R.string.error_default)
        binding.btnBack.setOnClickListener { finish() }
        binding.btnRetry.setOnClickListener {
            setResult(RESULT_OK)
            finish()
        }
    }

    companion object {
        private const val EXTRA_MESSAGE = "message"

        fun intent(context: Context, message: String?): Intent =
            Intent(context, ErrorActivity::class.java).putExtra(EXTRA_MESSAGE, message)
    }
}
