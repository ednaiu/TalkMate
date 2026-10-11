package ru.itmo.talkmate.ui

import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import ru.itmo.talkmate.Lang
import ru.itmo.talkmate.R
import ru.itmo.talkmate.ServiceLocator
import ru.itmo.talkmate.databinding.DialogProfileBinding

/** Настройки из личного кабинета: язык, адрес сервера и выход. */
object SettingsDialog {
    fun show(activity: AppCompatActivity, onLogout: () -> Unit) {
        val session = ServiceLocator.session
        val view = DialogProfileBinding.inflate(activity.layoutInflater)
        view.tvProfileName.text = session.userName
        view.tvProfileEmail.text = session.userEmail
        val names = listOf(activity.getString(R.string.language_system), activity.getString(R.string.language_ru), activity.getString(R.string.language_en))
        val tags = listOf(null, "ru", "en")
        view.btnLanguage.text = activity.getString(R.string.language_row, names[tags.indexOf(Lang.chosen()).coerceAtLeast(0)])
        view.btnLanguage.setOnClickListener {
            // Смена языка пересоздаёт экран: система или библиотека сами перечитывают ресурсы.
            MaterialAlertDialogBuilder(activity)
                .setTitle(R.string.language_title)
                .setItems(names.toTypedArray()) { _, which -> Lang.choose(tags[which]) }
                .show()
        }
        MaterialAlertDialogBuilder(activity)
            .setView(view.root)
            .setPositiveButton(R.string.logout) { _, _ -> onLogout() }
            .setNeutralButton(R.string.server) { _, _ -> ServerDialog.show(activity) }
            .setNegativeButton(R.string.close, null)
            .show()
    }
}
