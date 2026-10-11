import Foundation

/// Тексты для экрана результатов. Чистые функции без UIKit.
enum Formatters {
    static func rate(_ wordsPerMinute: Double) -> String {
        let value = Int(wordsPerMinute.rounded())
        return L("\(value) сл/мин", "\(value) wpm")
    }

    static func volume(_ level: String) -> String {
        switch level {
        case "quiet": return L("тихая", "quiet")
        case "loud": return L("громкая", "loud")
        default: return L("нормальная", "normal")
        }
    }

    static func slideStatus(_ status: String?) -> String {
        switch status {
        case "covered": return L("раскрыт", "covered")
        case "partly": return L("раскрыт частично", "partly covered")
        case "skipped": return L("не раскрыт", "not covered")
        case "retold": return L("пересказан своими словами", "retold in your own words")
        default: return L("без текста", "no text")
        }
    }

    /// Время, проведённое на слайде: минуты и секунды.
    static func slideTime(_ seconds: Int) -> String { String(format: "%d:%02d", seconds / 60, seconds % 60) }

    /// Вторая строка слайда в сводке: время, оценка и замечания к самому слайду.
    static func slideLine(_ item: SlideItem) -> String {
        var status = slideStatus(item.status)
        if let coverage = item.coverage, item.status == "covered" || item.status == "partly" { status += L(" на \(coverage)%", " \(coverage)%") }
        var parts = [slideTime(item.seconds ?? 0), status]
        if (item.reading ?? 0) >= 50 { parts.append(L("текст зачитан", "read aloud")) }
        if item.dense == true { parts.append(L("много текста", "too much text")) }
        if item.smallText == true { parts.append(L("мелкий шрифт", "small font")) }
        return parts.joined(separator: " · ")
    }

    static func slidesSummary(_ report: SlidesReport) -> String {
        let (pages, coverage, reading) = (report.pages ?? 0, report.coverage ?? 0, report.reading ?? 0)
        let summary = L("Слайдов: \(pages). Раскрыто словами \(coverage)% написанного, зачитано со слайдов \(reading)% речи",
                        "Slides: \(pages). You covered \(coverage)% of what is written on them and read \(reading)% of your speech off the slides")
        let timing = report.timed == true
            ? L("Время на слайд взято из ваших переключений.", "Time per slide comes from your own slide changes.")
            : L("Время на слайд оценено по словам. Чтобы оно было точным, листайте слайды в приложении во время записи.",
                "Time per slide is estimated from the words. To make it exact, flip the slides in the app while recording.")
        return summary + "\n" + timing
    }

    static func monotonyDescription(_ level: String) -> String { level == "monotone" ? L("монотонная", "monotone") : L("выразительная", "expressive") }

    static func emotion(_ label: String?) -> String {
        switch label {
        case "anger": return L("злость", "anger")
        case "disgust": return L("отвращение", "disgust")
        case "fear": return L("страх", "fear")
        case "happiness": return L("счастье", "happiness")
        case "enthusiasm": return L("интерес", "interest")
        case "sadness": return L("грусть", "sadness")
        case "neutral": return L("нейтральная", "neutral")
        default: return L("не определена", "not detected")
        }
    }

    static func clarity(_ score: Double?, _ level: String?) -> String {
        guard let score else { return L("не определена", "not detected") }
        let word: String
        switch level {
        case "clear": word = L("чёткая", "clear")
        case "unclear": word = L("невнятная", "unclear")
        default: word = L("средняя", "average")
        }
        return "\(word), \(Int(score.rounded()))%"
    }

    static func fillers(_ count: Int) -> String {
        L("\(count) \(plural(count, "слово", "слова", "слов"))", "\(count) \(count == 1 ? "word" : "words")")
    }

    static func plural(_ n: Int, _ one: String, _ few: String, _ many: String) -> String {
        let mod100 = n % 100, mod10 = n % 10
        if (11...14).contains(mod100) { return many }
        if mod10 == 1 { return one }
        if (2...4).contains(mod10) { return few }
        return many
    }

    /// Время записи с миллисекундами: ММ:СС.ммм.
    static func timer(_ seconds: TimeInterval) -> String {
        let millis = Int((seconds * 1000).rounded(.down))
        return String(format: "%02d:%02d.%03d", millis / 60_000, (millis / 1000) % 60, millis % 1000)
    }

    static func structure(_ level: String?) -> String {
        switch level {
        case "good": return L("хорошая", "good")
        case "partial": return L("частичная", "partial")
        case "weak": return L("слабая", "weak")
        default: return L("не оценена", "not rated")
        }
    }

    /// ГГГГ-ММ-ДД из ввода ДД.ММ.ГГГГ. Возвращает nil, если дата не разобрана.
    static func birthDateToISO(_ input: String) -> String? {
        let parts = input.trimmingCharacters(in: .whitespaces).split(separator: ".", omittingEmptySubsequences: false)
        guard parts.count == 3, parts[2].count == 4, (1...2).contains(parts[0].count), (1...2).contains(parts[1].count),
              let day = Int(parts[0]), let month = Int(parts[1]), let year = Int(parts[2]),
              parts.allSatisfy({ $0.allSatisfy(\.isNumber) }),
              (1...12).contains(month), day >= 1, year >= 1900 else { return nil }
        let leap = year % 4 == 0 && (year % 100 != 0 || year % 400 == 0)
        let days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
        guard day <= days else { return nil }
        return String(format: "%04d-%02d-%02d", year, month, day)
    }

    /// Короткая подпись даты для оси графика: ДД.ММ из ISO-строки.
    private static let monthsRu = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    private static let monthsEn = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

    /// День и месяц из даты сервера: «10 октября», коротко «10 окт». По-английски «October 10» и «Oct 10».
    static func dayMonth(_ iso: String, short: Bool = false) -> String {
        let parts = iso.prefix(10).split(separator: "-")
        guard parts.count == 3, let month = Int(parts[1]), let day = Int(parts[2]), (1...12).contains(month) else { return iso }
        var name = (Lang.english ? monthsEn : monthsRu)[month - 1]
        if short { name = String(name.prefix(3)) }
        return Lang.english ? "\(name) \(day)" : "\(day) \(name)"
    }

    /// Подпись тренировки в списке: дата и длительность.
    static func trainingMeta(_ item: TrainingBrief) -> String {
        let minutes = max(1, Int((Double(item.duration) / 60).rounded()))
        return dayMonth(item.date) + " · " + L("\(minutes) мин", "\(minutes) min")
    }

    static func trainingsWord(_ n: Int) -> String { L(plural(n, "тренировка", "тренировки", "тренировок"), n == 1 ? "session" : "sessions") }

    static func minutesWord(_ n: Int) -> String {
        L(plural(n, "минута практики", "минуты практики", "минут практики"), n == 1 ? "minute of practice" : "minutes of practice")
    }

    static func streakWord(_ n: Int) -> String { L(plural(n, "день подряд", "дня подряд", "дней подряд"), n == 1 ? "day in a row" : "days in a row") }

    static func lastTrainings(_ n: Int) -> String {
        n == 1 ? L("Последняя тренировка", "Last session")
            : L("Последние \(n) \(plural(n, "тренировка", "тренировки", "тренировок"))", "Last \(n) sessions")
    }

    static func wordsPerMinute(_ n: Int) -> String { L(plural(n, "слово в минуту", "слова в минуту", "слов в минуту"), "words per minute") }

    static func shortDate(_ iso: String) -> String {
        let parts = iso.prefix(10).split(separator: "-")
        guard parts.count == 3, parts[0].count == 4 else { return iso }
        return "\(parts[2]).\(parts[1])"
    }

    static func number(_ value: Double, decimals: Int) -> String {
        decimals == 0 ? "\(Int(value.rounded()))" : String(format: "%.\(decimals)f", locale: Locale(identifier: "ru_RU"), value)
    }
}

/// Проверка полей форм до отправки на сервер. Возвращает текст ошибки или nil.
enum Validation {
    static let minPassword = 6

    static func name(_ value: String) -> String? {
        value.trimmingCharacters(in: .whitespaces).isEmpty ? L("Введите имя", "Enter your name") : nil
    }

    static func email(_ value: String) -> String? {
        let trimmed = value.trimmingCharacters(in: .whitespaces)
        if trimmed.isEmpty { return L("Введите email", "Enter your email") }
        return trimmed.range(of: #"^[^@\s]+@[^@\s]+\.[^@\s]+$"#, options: .regularExpression) == nil ? L("Введите корректный email", "Enter a valid email") : nil
    }

    static func password(_ value: String) -> String? {
        if value.isEmpty { return L("Введите пароль", "Enter a password") }
        return value.count < minPassword ? L("Пароль должен быть не короче \(minPassword) символов", "The password must be at least \(minPassword) characters long") : nil
    }

    static func code(_ value: String) -> String? {
        value.trimmingCharacters(in: .whitespaces).range(of: #"^\d{6}$"#, options: .regularExpression) == nil ? L("Введите код из шести цифр", "Enter the six-digit code") : nil
    }

    static func birthDate(_ value: String) -> String? {
        let trimmed = value.trimmingCharacters(in: .whitespaces)
        return trimmed.isEmpty || Formatters.birthDateToISO(trimmed) != nil ? nil : L("Дата рождения в формате ДД.ММ.ГГГГ", "Date of birth must be DD.MM.YYYY")
    }

    static func serverURL(_ value: String) -> String? {
        value.trimmingCharacters(in: .whitespaces).range(of: #"^https?://[^\s/]+(:\d+)?(/.*)?$"#, options: .regularExpression) == nil
            ? L("Адрес должен начинаться с http:// или https://", "The address must start with http:// or https://") : nil
    }
}

/// Пометки над фразой расшифровки: что в ней не так с темпом и какая слышна окраска.
enum TranscriptMarks {
    enum Kind { case tempo, negativeEmotion, emotion }

    struct Mark: Equatable {
        let text: String
        let kind: Kind
    }

    private static let negative: Set<String> = ["anger", "disgust", "fear", "sadness"]

    static func marks(_ segment: Segment) -> [Mark] {
        var result: [Mark] = []
        if segment.rateStatus == "fast" { result.append(Mark(text: L("быстро", "fast") + ", \(Formatters.rate(segment.rate))", kind: .tempo)) }
        if segment.rateStatus == "slow" { result.append(Mark(text: L("медленно", "slow") + ", \(Formatters.rate(segment.rate))", kind: .tempo)) }
        if segment.clarityLevel == "unclear" {
            let percent = segment.clarity.map { ", \(Int($0.rounded()))%" } ?? ""
            result.append(Mark(text: L("невнятно", "unclear") + percent, kind: .negativeEmotion))
        }
        if let emotion = segment.emotion, emotion != "neutral" {
            result.append(Mark(text: Formatters.emotion(emotion), kind: negative.contains(emotion) ? .negativeEmotion : .emotion))
        }
        return result
    }

    /// Сколько фраз с замечаниями: для строки-пояснения над расшифровкой.
    static func summary(_ segments: [Segment]) -> String {
        let tempo = segments.filter { $0.rateStatus != "normal" }.count
        let emotion = segments.filter { negative.contains($0.emotion ?? "") }.count
        let fillers = segments.reduce(0) { $0 + $1.parts.filter(\.filler).count }
        var notes: [String] = []
        if fillers > 0 { notes.append(L("заполнителей: \(fillers)", "filler words: \(fillers)")) }
        if tempo > 0 { notes.append(L("\(Formatters.plural(tempo, "фраза", "фразы", "фраз")) с темпом вне нормы: \(tempo)", "phrases with the pace off the norm: \(tempo)")) }
        let unclear = segments.filter { $0.clarityLevel == "unclear" }.count
        if unclear > 0 { notes.append(L("\(Formatters.plural(unclear, "невнятная фраза", "невнятные фразы", "невнятных фраз")): \(unclear)", "unclear phrases: \(unclear)")) }
        if emotion > 0 { notes.append(L("\(Formatters.plural(emotion, "фраза", "фразы", "фраз")) с отрицательной окраской: \(emotion)", "phrases with a negative tone: \(emotion)")) }
        guard !notes.isEmpty else { return L("Замечаний по фразам нет", "No remarks on the phrases") }
        let joined = notes.joined(separator: "; ")
        return joined.prefix(1).uppercased() + joined.dropFirst()
    }
}

/// Разметка текстов статей и рекомендаций: фрагмент между ** и ** выделяется жирным.
enum Markup {
    struct Segment: Equatable {
        let text: String
        let bold: Bool
    }

    static func parse(_ source: String) -> [Segment] {
        let parts = source.components(separatedBy: "**")
        // Непарная пара звёздочек: считаем текст обычным, чтобы не потерять символы.
        if parts.count % 2 == 0 { return source.isEmpty ? [] : [Segment(text: source, bold: false)] }
        return parts.enumerated().compactMap { index, text in
            text.isEmpty ? nil : Segment(text: text, bold: index % 2 == 1)
        }
    }

    static func plain(_ source: String) -> String { parse(source).map(\.text).joined() }
}
