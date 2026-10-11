package ru.itmo.talkmate.ui

import android.os.Bundle
import android.view.LayoutInflater
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import ru.itmo.talkmate.R
import ru.itmo.talkmate.data.ArticleSummary
import ru.itmo.talkmate.databinding.ActivityArticlesBinding

class ArticlesActivity : BaseActivity() {
    private lateinit var binding: ActivityArticlesBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityArticlesBinding.inflate(layoutInflater)
        setContentView(binding.root)
        load()
    }

    override fun onRetry() = load()

    private fun load() {
        call(progress = binding.progress, request = { it.articles() }) { articles ->
            binding.rvArticles.adapter = Adapter(articles) { startActivity(ArticleActivity.intent(this, it)) }
        }
    }

    private class Adapter(
        private val items: List<ArticleSummary>,
        private val onClick: (ArticleSummary) -> Unit,
    ) : RecyclerView.Adapter<Adapter.Holder>() {

        class Holder(val title: TextView) : RecyclerView.ViewHolder(title)

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) =
            Holder(LayoutInflater.from(parent.context).inflate(R.layout.item_article, parent, false) as TextView)

        override fun getItemCount() = items.size

        override fun onBindViewHolder(holder: Holder, position: Int) {
            holder.title.text = items[position].title
            holder.title.setOnClickListener { onClick(items[position]) }
        }
    }
}
