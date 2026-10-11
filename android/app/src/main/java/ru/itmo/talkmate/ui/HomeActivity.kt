package ru.itmo.talkmate.ui

import android.content.Intent
import android.os.Bundle
import ru.itmo.talkmate.R
import ru.itmo.talkmate.databinding.ActivityHomeBinding

class HomeActivity : BaseActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!session.isLoggedIn) {
            logout()
            return
        }
        val binding = ActivityHomeBinding.inflate(layoutInflater)
        setContentView(binding.root)
        binding.tvWelcomeMessage.text = getString(R.string.welcome_user, session.userName)
        binding.cardTraining.setOnClickListener { startActivity(Intent(this, RecordActivity::class.java)) }
        binding.btnStartTraining.setOnClickListener { startActivity(Intent(this, RecordActivity::class.java)) }
        binding.cardArticles.setOnClickListener { startActivity(Intent(this, ArticlesActivity::class.java)) }
        binding.cardStats.setOnClickListener { startActivity(Intent(this, StatsActivity::class.java)) }
        binding.btnProfile.setOnClickListener { openTab(ProfileActivity::class.java) }
        setupBottomNav(R.id.navHome)
    }
}
