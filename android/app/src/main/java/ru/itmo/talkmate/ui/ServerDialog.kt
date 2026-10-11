package ru.itmo.talkmate.ui

import android.text.InputType
import android.widget.EditText
import android.widget.FrameLayout
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import ru.itmo.talkmate.R
import ru.itmo.talkmate.ServiceLocator

/** Диалог с адресом сервера. Нужен, когда приложение запускают на телефоне, а сервер стоит в локальной сети. */
object ServerDialog {
    fun show(activity: AppCompatActivity) {
        val input = EditText(activity).apply {
            id = R.id.etServerUrl
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
            setText(ServiceLocator.session.serverUrl)
            setSingleLine()
        }
        val padding = (20 * activity.resources.displayMetrics.density).toInt()
        val holder = FrameLayout(activity).apply {
            setPadding(padding, padding / 2, padding, 0)
            addView(input)
        }
        val dialog = MaterialAlertDialogBuilder(activity)
            .setTitle(R.string.server)
            .setView(holder)
            .setPositiveButton(R.string.save, null)
            .setNegativeButton(R.string.cancel, null)
            .create()
        dialog.setOnShowListener {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                val error = Validation.serverUrl(input.text.toString())
                if (error != null) {
                    input.error = error
                } else {
                    ServiceLocator.session.serverUrl = input.text.toString()
                    dialog.dismiss()
                }
            }
        }
        dialog.show()
    }
}
