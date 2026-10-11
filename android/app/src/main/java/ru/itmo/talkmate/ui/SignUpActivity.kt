package ru.itmo.talkmate.ui

import android.app.DatePickerDialog
import android.content.Intent
import android.os.Bundle
import android.view.View
import ru.itmo.talkmate.data.RegisterRequest
import ru.itmo.talkmate.databinding.ActivitySignUpBinding
import java.util.Calendar
import java.util.Locale

class SignUpActivity : BaseActivity() {
    private lateinit var binding: ActivitySignUpBinding
    private var gender: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySignUpBinding.inflate(layoutInflater)
        setContentView(binding.root)
        gender = savedInstanceState?.getString(KEY_GENDER)
        showGender()
        binding.btnMale.setOnClickListener { toggleGender("male") }
        binding.btnFemale.setOnClickListener { toggleGender("female") }
        binding.btnRegister.setOnClickListener { submit() }
        bindPasswordToggle(binding.etPassword, binding.btnTogglePassword)
        binding.btnPickDate.setOnClickListener { pickBirthDate() }
        binding.tvLogin.setOnClickListener {
            startActivity(Intent(this, LoginActivity::class.java))
            finish()
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        outState.putString(KEY_GENDER, gender)
    }

    /** Календарь заполняет поле в том же формате, в каком дату вводят вручную. */
    private fun pickBirthDate() {
        val start = Calendar.getInstance().get(Calendar.YEAR) - 20
        DatePickerDialog(this, { _, year, month, day ->
            binding.etBirthDate.setText(String.format(Locale.US, "%02d.%02d.%04d", day, month + 1, year))
        }, start, 0, 1).apply { datePicker.maxDate = System.currentTimeMillis() }.show()
    }

    private fun toggleGender(value: String) {
        gender = if (gender == value) null else value
        showGender()
    }

    private fun showGender() {
        binding.btnMale.isSelected = gender == "male"
        binding.btnFemale.isSelected = gender == "female"
    }

    private fun submit() {
        val name = binding.etName.text.toString().trim()
        val email = binding.etEmail.text.toString().trim()
        val password = binding.etPassword.text.toString()
        val birth = binding.etBirthDate.text.toString().trim()
        val problem = Validation.name(name) ?: Validation.email(email) ?: Validation.password(password) ?: Validation.birthDate(birth)
        if (problem != null) {
            showError(problem)
            return
        }
        showError(null)
        binding.btnRegister.isEnabled = false
        val request = RegisterRequest(
            name = name,
            email = email,
            password = password,
            phone = binding.etPhone.text.toString().trim(),
            birthDate = Formatters.birthDateToIso(birth),
            gender = gender,
        )
        call(
            progress = binding.progress,
            onError = {
                binding.btnRegister.isEnabled = true
                showError(it.message)
            },
            request = { it.register(request) },
        ) { result ->
            session.save(result)
            openHome()
        }
    }

    private fun showError(text: String?) {
        binding.tvError.text = text
        binding.tvError.visibility = if (text == null) View.GONE else View.VISIBLE
    }

    private companion object {
        const val KEY_GENDER = "gender"
    }
}
