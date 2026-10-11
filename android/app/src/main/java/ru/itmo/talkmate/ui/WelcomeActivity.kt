package ru.itmo.talkmate.ui

import android.content.Intent
import android.os.Bundle
import androidx.core.content.ContextCompat
import ru.itmo.talkmate.R
import ru.itmo.talkmate.databinding.ActivityWelcomeBinding

class WelcomeActivity : BaseActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (session.isLoggedIn) {
            openHome()
            return
        }
        val binding = ActivityWelcomeBinding.inflate(layoutInflater)
        setContentView(binding.root)
        // Фон экрана светлый, поэтому полоса состояния красится в него, а не в розовый цвет темы.
        window.statusBarColor = ContextCompat.getColor(this, R.color.paper)
        binding.btnLogin.setOnClickListener { startActivity(Intent(this, LoginActivity::class.java)) }
        binding.btnRegistration.setOnClickListener { startActivity(Intent(this, SignUpActivity::class.java)) }
        binding.logo.setOnLongClickListener {
            ServerDialog.show(this)
            true
        }
    }
}
