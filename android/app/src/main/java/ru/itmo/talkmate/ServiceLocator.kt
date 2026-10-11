package ru.itmo.talkmate

import android.content.Context
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import ru.itmo.talkmate.audio.Recorder
import ru.itmo.talkmate.audio.WavRecorder
import ru.itmo.talkmate.data.Api
import ru.itmo.talkmate.data.HttpApi
import ru.itmo.talkmate.data.SessionStore

/** Точка сборки зависимостей. Автотесты подменяют здесь сервер, диктофон и диспетчер. */
object ServiceLocator {
    lateinit var session: SessionStore
        private set

    lateinit var api: Api
    var recorderFactory: () -> Recorder = { WavRecorder() }
    var io: CoroutineDispatcher = Dispatchers.IO

    fun init(context: Context) {
        session = SessionStore(context.applicationContext)
        api = HttpApi(baseUrl = { session.serverUrl }, token = { session.token })
        recorderFactory = { WavRecorder() }
        io = Dispatchers.IO
    }
}
