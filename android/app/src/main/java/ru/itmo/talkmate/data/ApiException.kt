package ru.itmo.talkmate.data

class ApiException(val kind: Kind, message: String, val code: String = "") : Exception(message) {
    enum class Kind {
        /** Нет связи с сервером. */
        NETWORK,

        /** Токен отсутствует или истёк. */
        UNAUTHORIZED,

        /** Сервер отклонил запрос: ошибка ввода, занятый email, плохая запись. */
        REJECTED,

        /** Сбой на стороне сервера. */
        SERVER,
    }
}
