import Foundation

/// Язык интерфейса: русский или английский. Выбирается в профиле; если не выбран, берётся язык телефона.
/// Всё, что не русский, показывается по-английски.
enum Lang {
    private static let key = "appLanguage"

    /// Язык, заданный в обход настроек. Модульные тесты написаны для русского интерфейса и получают его всегда.
    static var forced: String? = ProcessInfo.processInfo.environment["XCTestConfigurationFilePath"] != nil ? "ru" : nil

    /// Выбор пользователя: ru, en или nil, если приложение следует за телефоном.
    static var chosen: String? {
        get { UserDefaults.standard.string(forKey: key) }
        set { UserDefaults.standard.set(newValue, forKey: key) }
    }

    static var system: String { (Locale.preferredLanguages.first ?? "en").hasPrefix("ru") ? "ru" : "en" }

    /// Код языка для сервера: на нём он пишет рекомендации и сообщения об ошибках.
    static var code: String { forced ?? chosen ?? system }

    static var english: Bool { code != "ru" }

    static var chosenName: String {
        switch chosen {
        case "ru": return "Русский"
        case "en": return "English"
        default: return L("как в системе", "system default")
        }
    }
}

/// Текст на языке интерфейса.
func L(_ russian: String, _ english: String) -> String { Lang.english ? english : russian }
