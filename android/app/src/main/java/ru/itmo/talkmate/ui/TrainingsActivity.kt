package ru.itmo.talkmate.ui

import android.os.Bundle
import android.view.View
import ru.itmo.talkmate.R
import ru.itmo.talkmate.databinding.ActivityTrainingsBinding

/** Все тренировки пользователя. Нажатие открывает разбор записи. */
class TrainingsActivity : BaseActivity() {
    private lateinit var binding: ActivityTrainingsBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityTrainingsBinding.inflate(layoutInflater)
        setContentView(binding.root)
        setupBottomNav(R.id.navTrainings)
    }

    override fun onResume() {
        super.onResume()
        load()
    }

    override fun onRetry() = load()

    private fun load() {
        call(progress = binding.progress, request = { it.trainings() }) { items ->
            binding.tvEmpty.visibility = if (items.isEmpty()) View.VISIBLE else View.GONE
            showTrainings(binding.trainingsList, items)
        }
    }
}
