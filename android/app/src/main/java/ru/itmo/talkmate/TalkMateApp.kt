package ru.itmo.talkmate

import android.app.Application

class TalkMateApp : Application() {
    override fun onCreate() {
        super.onCreate()
        ServiceLocator.init(this)
    }
}
