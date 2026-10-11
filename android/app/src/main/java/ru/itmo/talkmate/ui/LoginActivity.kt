package ru.itmo.talkmate.ui

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.view.inputmethod.EditorInfo
import ru.itmo.talkmate.Lang
import ru.itmo.talkmate.databinding.ActivityLoginBinding

class LoginActivity : BaseActivity() {
    private lateinit var binding: ActivityLoginBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityLoginBinding.inflate(layoutInflater)
        setContentView(binding.root)
        binding.btnLogin.setOnClickListener { submit() }
        bindPasswordToggle(binding.etPassword, binding.btnTogglePassword)
        binding.tvCreateAccount.setOnClickListener {
            startActivity(Intent(this, SignUpActivity::class.java))
            finish()
        }
        binding.tvForgot.setOnClickListener {
            startActivity(ResetPasswordActivity.intent(this, binding.etEmail.text.toString().trim()))
        }
        binding.etPassword.setOnEditorActionListener { _, action, _ ->
            if (action == EditorInfo.IME_ACTION_DONE) submit()
            false
        }
    }

    private fun submit() {
        val email = binding.etEmail.text.toString().trim()
        val password = binding.etPassword.text.toString()
        val problem = Validation.email(email) ?: if (password.isEmpty()) Lang.t("Введите пароль", "Enter your password") else null
        if (problem != null) {
            showError(problem)
            return
        }
        showError(null)
        binding.btnLogin.isEnabled = false
        call(
            progress = binding.progress,
            onError = {
                binding.btnLogin.isEnabled = true
                showError(it.message)
            },
            request = { it.login(email, password) },
        ) { result ->
            session.save(result)
            openHome()
        }
    }

    private fun showError(text: String?) {
        binding.tvError.text = text
        binding.tvError.visibility = if (text == null) View.GONE else View.VISIBLE
    }
}
