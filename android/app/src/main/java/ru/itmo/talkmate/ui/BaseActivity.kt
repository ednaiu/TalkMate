package ru.itmo.talkmate.ui

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import ru.itmo.talkmate.Lang
import ru.itmo.talkmate.R
import ru.itmo.talkmate.ServiceLocator
import ru.itmo.talkmate.data.Api
import ru.itmo.talkmate.data.ApiException
import ru.itmo.talkmate.data.TrainingBrief

abstract class BaseActivity : AppCompatActivity() {
    protected val session get() = ServiceLocator.session

    override fun attachBaseContext(newBase: Context) = super.attachBaseContext(Lang.wrap(newBase))

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Lang.sync(this)
    }

    override fun onPostCreate(savedInstanceState: Bundle?) {
        super.onPostCreate(savedInstanceState)
        // Кнопка «назад» есть в вёрстке всех внутренних экранов и работает одинаково.
        findViewById<View?>(R.id.btnBack)?.setOnClickListener { onBackPressedDispatcher.onBackPressed() }
    }

    private val errorScreen = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == RESULT_OK) onRetry() else onErrorDismissed()
    }

    /** Пользователь нажал «Попробовать снова» на экране ошибки. */
    protected open fun onRetry() {}

    /** Пользователь ушёл с экрана ошибки назад. По умолчанию закрываем и текущий экран: показывать на нём нечего. */
    protected open fun onErrorDismissed() = finish()

    /**
     * Выполняет запрос к серверу вне главного потока.
     * Истёкшая сессия всегда ведёт на экран входа, остальные ошибки получает [onError].
     */
    protected fun <T> call(
        progress: View? = null,
        onError: (ApiException) -> Unit = ::showErrorScreen,
        request: (Api) -> T,
        onSuccess: (T) -> Unit,
    ) {
        lifecycleScope.launch {
            progress?.visibility = View.VISIBLE
            val outcome = try {
                Result.success(withContext(ServiceLocator.io) { request(ServiceLocator.api) })
            } catch (e: ApiException) {
                Result.failure(e)
            } catch (e: Exception) {
                Result.failure(ApiException(ApiException.Kind.SERVER, getString(R.string.error_default)))
            }
            progress?.visibility = View.INVISIBLE
            outcome.onSuccess(onSuccess).onFailure { error ->
                error as ApiException
                if (error.kind == ApiException.Kind.UNAUTHORIZED) {
                    Toast.makeText(this@BaseActivity, R.string.session_expired, Toast.LENGTH_LONG).show()
                    logout()
                } else {
                    onError(error)
                }
            }
        }
    }

    /** Нижняя панель разделов: подсвечивает текущий и переключает на остальные. */
    protected fun setupBottomNav(selected: Int) {
        val tabs = listOf(R.id.navHome to HomeActivity::class.java, R.id.navTrainings to TrainingsActivity::class.java,
            R.id.navProfile to ProfileActivity::class.java)
        for ((id, target) in tabs) {
            val item = findViewById<ViewGroup>(id) ?: continue
            val color = ContextCompat.getColor(this, if (id == selected) R.color.blue_strong else R.color.grey_text)
            (item.getChildAt(0) as ImageView).setColorFilter(color)
            (item.getChildAt(1) as TextView).setTextColor(color)
            item.isSelected = id == selected
            item.setOnClickListener { if (id != selected) openTab(target) }
        }
    }

    /** Переход между разделами без анимации: экран уже открытого раздела поднимается наверх, а не создаётся заново. */
    protected fun openTab(target: Class<*>) {
        startActivity(Intent(this, target).addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT))
        overridePendingTransition(0, 0)
    }

    /** Строки тренировок в списке. Нажатие загружает разбор и открывает экран результатов. */
    protected fun showTrainings(list: LinearLayout, items: List<TrainingBrief>) {
        list.removeAllViews()
        for (item in items) {
            val row = layoutInflater.inflate(R.layout.item_training, list, false)
            row.findViewById<TextView>(R.id.tvTrainingTitle).text = item.title
            row.findViewById<TextView>(R.id.tvTrainingMeta).text = Formatters.trainingMeta(item.date, item.durationSec)
            row.setOnClickListener {
                call(request = { it.speech(item.id) }) { result -> startActivity(ResultsActivity.intent(this, result)) }
            }
            list.addView(row)
        }
    }

    protected fun showErrorScreen(error: ApiException) {
        errorScreen.launch(ErrorActivity.intent(this, error.message))
    }

    protected fun logout() {
        session.clear()
        startActivity(Intent(this, WelcomeActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK))
        finish()
    }

    protected fun openHome() {
        startActivity(Intent(this, HomeActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK))
        finish()
    }
}
