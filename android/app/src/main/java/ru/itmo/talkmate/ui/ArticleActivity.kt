package ru.itmo.talkmate.ui

import android.content.Context
import android.content.Intent
import android.os.Bundle
import androidx.core.content.ContextCompat
import ru.itmo.talkmate.R
import ru.itmo.talkmate.data.ArticleSummary
import ru.itmo.talkmate.databinding.ActivityArticleBinding

class ArticleActivity : BaseActivity() {
    private lateinit var binding: ActivityArticleBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityArticleBinding.inflate(layoutInflater)
        setContentView(binding.root)
        binding.tvArticleTitle.text = intent.getStringExtra(EXTRA_TITLE)
        load()
    }

    override fun onRetry() = load()

    private fun load() {
        val id = intent.getIntExtra(EXTRA_ID, -1)
        call(progress = binding.progress, request = { it.article(id) }) { article ->
            binding.tvArticleTitle.text = article.title
            binding.tvArticleContent.text = Markup.render(article.content, ContextCompat.getColor(this, R.color.ink))
        }
    }

    companion object {
        private const val EXTRA_ID = "id"
        private const val EXTRA_TITLE = "title"

        fun intent(context: Context, article: ArticleSummary): Intent =
            Intent(context, ArticleActivity::class.java).putExtra(EXTRA_ID, article.id).putExtra(EXTRA_TITLE, article.title)
    }
}
