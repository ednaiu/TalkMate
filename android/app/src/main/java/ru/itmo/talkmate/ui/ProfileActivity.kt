package ru.itmo.talkmate.ui

import android.content.Intent
import android.os.Bundle
import android.view.View
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import ru.itmo.talkmate.R
import ru.itmo.talkmate.data.Profile
import ru.itmo.talkmate.databinding.ActivityProfileBinding

/** Личный кабинет: счётчики тренировок, темп последних записей и список недавних тренировок. */
class ProfileActivity : BaseActivity() {
    private lateinit var binding: ActivityProfileBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityProfileBinding.inflate(layoutInflater)
        setContentView(binding.root)
        setupBottomNav(R.id.navProfile)
        showName(session.userName)
        binding.btnSettings.setOnClickListener { SettingsDialog.show(this) { logout() } }
        binding.btnStartTraining.setOnClickListener { startActivity(Intent(this, RecordActivity::class.java)) }
        binding.tvAll.setOnClickListener { openTab(TrainingsActivity::class.java) }
        binding.cardPlans.setOnClickListener {
            MaterialAlertDialogBuilder(this).setMessage(R.string.plans_message).setPositiveButton(R.string.close, null).show()
        }
    }

    override fun onResume() {
        super.onResume()
        load()   // после новой тренировки счётчики должны обновиться
    }

    override fun onRetry() = load()

    private fun load() {
        call(progress = binding.progress, request = { it.profile() }) { show(it) }
    }

    private fun showName(name: String) {
        binding.tvName.text = name
        binding.tvAvatar.text = name.trim().take(1).uppercase()
    }

    private fun show(profile: Profile) {
        if (profile.name.isNotBlank()) showName(profile.name)
        binding.tvCount.text = profile.count.toString()
        binding.tvCountCaption.text = Formatters.trainingsWord(profile.count)
        binding.tvMinutes.text = profile.minutes.toString()
        binding.tvMinutesCaption.text = Formatters.minutesWord(profile.minutes)
        binding.tvStreak.text = profile.streak.toString()
        binding.tvStreakCaption.text = Formatters.streakWord(profile.streak)

        if (profile.tempo.isEmpty()) {
            binding.tempoRow.visibility = View.GONE
            binding.tvTempoPeriod.setText(R.string.tempo_empty)
        } else {
            val last = profile.tempo.last().rate
            binding.tempoRow.visibility = View.VISIBLE
            binding.tvTempoPeriod.text = Formatters.lastTrainings(profile.tempo.size)
            binding.tvTempoValue.text = last.toString()
            binding.tvTempoCaption.text = Formatters.wordsPerMinute(last)
            binding.tempoChart.show(profile.tempo.map { it.rate }, profile.tempo.map { Formatters.dayMonth(it.date, short = true) },
                profile.rateSlow, profile.rateFast)
        }
        binding.tvRecentEmpty.visibility = if (profile.recent.isEmpty()) View.VISIBLE else View.GONE
        showTrainings(binding.recentList, profile.recent)
    }
}
