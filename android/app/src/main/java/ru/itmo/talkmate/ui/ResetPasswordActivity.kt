package ru.itmo.talkmate.ui

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.View
import ru.itmo.talkmate.R
import ru.itmo.talkmate.databinding.ActivityResetPasswordBinding

/** Восстановление пароля в два шага: запросить код на почту, затем ввести код и новый пароль. */
class ResetPasswordActivity : BaseActivity() {
    private lateinit var binding: ActivityResetPasswordBinding
    private var codeRequestedFor: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityResetPasswordBinding.inflate(layoutInflater)
        setContentView(binding.root)
        binding.etEmail.setText(intent.getStringExtra(EXTRA_EMAIL))
        codeRequestedFor = savedInstanceState?.getString(KEY_EMAIL)
        binding.btnSendCode.setOnClickListener { requestCode() }
        binding.btnResetPassword.setOnClickListener { changePassword() }
        render()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        outState.putString(KEY_EMAIL, codeRequestedFor)
    }

    private fun requestCode() {
        val email = binding.etEmail.text.toString().trim()
        Validation.email(email)?.let { return showError(it) }
        showError(null)
        setBusy(true)
        call(
            progress = binding.progress,
            onError = {
                setBusy(false)
                showError(it.message)
            },
            request = { it.requestPasswordReset(email) },
        ) {
            setBusy(false)
            codeRequestedFor = email
            render()
        }
    }

    private fun changePassword() {
        val email = codeRequestedFor ?: return
        val code = binding.etCode.text.toString().trim()
        val password = binding.etNewPassword.text.toString()
        (Validation.code(code) ?: Validation.password(password))?.let { return showError(it) }
        showError(null)
        setBusy(true)
        call(
            progress = binding.progress,
            onError = {
                setBusy(false)
                showError(it.message)
            },
            request = { it.resetPassword(email, code, password) },
        ) { result ->
            session.save(result)
            openHome()
        }
    }

    private fun render() {
        val waitingForCode = codeRequestedFor != null
        val step = if (waitingForCode) View.VISIBLE else View.GONE
        binding.tvInfo.visibility = step
        binding.etCode.visibility = step
        binding.etNewPassword.visibility = step
        binding.btnResetPassword.visibility = step
        binding.etEmail.isEnabled = !waitingForCode
        binding.tvInfo.text = getString(R.string.code_sent, codeRequestedFor.orEmpty())
        binding.btnSendCode.setText(if (waitingForCode) R.string.send_code_again else R.string.send_code)
    }

    private fun setBusy(busy: Boolean) {
        binding.btnSendCode.isEnabled = !busy
        binding.btnResetPassword.isEnabled = !busy
    }

    private fun showError(text: String?) {
        binding.tvError.text = text
        binding.tvError.visibility = if (text == null) View.GONE else View.VISIBLE
    }

    companion object {
        private const val EXTRA_EMAIL = "email"
        private const val KEY_EMAIL = "code_requested_for"

        fun intent(context: Context, email: String): Intent =
            Intent(context, ResetPasswordActivity::class.java).putExtra(EXTRA_EMAIL, email)
    }
}
