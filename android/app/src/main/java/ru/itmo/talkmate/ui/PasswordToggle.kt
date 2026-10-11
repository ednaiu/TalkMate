package ru.itmo.talkmate.ui

import android.text.method.PasswordTransformationMethod
import android.widget.EditText
import android.widget.ImageButton
import ru.itmo.talkmate.R

/** Кнопка с глазом в поле пароля: показывает и снова скрывает введённые символы. */
fun bindPasswordToggle(field: EditText, button: ImageButton) {
    button.setOnClickListener {
        val hidden = field.transformationMethod is PasswordTransformationMethod
        val cursor = field.selectionEnd.coerceAtLeast(0)
        field.transformationMethod = if (hidden) null else PasswordTransformationMethod.getInstance()
        field.setSelection(cursor)
        button.setImageResource(if (hidden) R.drawable.ic_eye else R.drawable.ic_eye_off)
        button.contentDescription = button.context.getString(if (hidden) R.string.hide_password else R.string.show_password)
    }
}
