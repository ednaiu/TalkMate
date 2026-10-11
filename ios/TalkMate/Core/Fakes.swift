#if DEBUG
import Foundation

/// Сервер в памяти для UI-тестов. Включается аргументом запуска -uiTesting, поведение задают переменные окружения.
final class FakeApi: Api {
    private var failures: [ApiError]
    private var accounts: [String: (password: String, name: String)] = ["edna@itmo.ru": ("secret1", "Эдна")]
    private let withStats: Bool
    private let monotone: Bool

    init(environment: [String: String]) {
        failures = (environment["FAKE_FAIL"] ?? "").split(separator: ",").compactMap { kind in
            switch kind {
            case "network": return ApiError.network
            case "server": return ApiError(kind: .server, message: "Сервис распознавания речи недоступен")
            case "unauthorized": return ApiError(kind: .unauthorized, message: "Сессия истекла, войдите снова")
            default: return nil
            }
        }
        withStats = environment["FAKE_STATS"] == "1"
        monotone = environment["FAKE_MONOTONE"] == "1"
    }

    static let articleList = [
        Article(id: 1, title: "Жестикуляция и движение", content: "Жестикуляция состоит из пяти основных жестов: **толкание, вытягивание, подъём, бросание и разрывание.** Каждое из них можно выполнить в шести направлениях."),
        Article(id: 2, title: "Подготовка на площадке", content: "Приходите в зал за полчаса до начала."),
        Article(id: 3, title: "Использование презентаций", content: "Одна мысль на слайд."),
        Article(id: 4, title: "Разогрев", content: "Голос работает как мышца."),
    ]

    private func maybeFail() throws {
        if !failures.isEmpty { throw failures.removeFirst() }
    }

    func register(_ request: RegisterRequest) async throws -> AuthResult {
        try maybeFail()
        if accounts[request.email] != nil {
            throw ApiError(kind: .rejected, message: "Пользователь с таким email уже зарегистрирован", code: "email_taken")
        }
        accounts[request.email] = (request.password, request.name)
        return AuthResult(token: "token", user: User(id: 2, name: request.name, email: request.email))
    }

    func login(email: String, password: String) async throws -> AuthResult {
        try maybeFail()
        guard let account = accounts[email], account.password == password else {
            throw ApiError(kind: .rejected, message: "Неверный email или пароль", code: "invalid_credentials")
        }
        return AuthResult(token: "token", user: User(id: 1, name: account.name, email: email))
    }

    func requestPasswordReset(email: String) async throws {
        try maybeFail()
    }

    func resetPassword(email: String, code: String, newPassword: String) async throws -> AuthResult {
        try maybeFail()
        guard let account = accounts[email], code == "123456" else {
            throw ApiError(kind: .rejected, message: "Неверный или просроченный код. Запросите новый", code: "invalid_code")
        }
        accounts[email] = (newPassword, account.name)
        return AuthResult(token: "token", user: User(id: 1, name: account.name, email: email))
    }

    func articles() async throws -> [ArticleSummary] {
        try maybeFail()
        return Self.articleList.map { ArticleSummary(id: $0.id, title: $0.title) }
    }

    func article(id: Int) async throws -> Article {
        try maybeFail()
        return Self.articleList.first { $0.id == id }!
    }

    func uploadSpeech(file: URL, slides: URL?, marks: [SlideMark]) async throws -> SpeechResult {
        try maybeFail()
        // Значения с экрана результатов из макета.
        let feedback = monotone
            ? Feedback(speechRate: 96, volume: "loud", monotony: "monotone", numFillers: 1, fillers: [], emotion: nil)
            : Feedback(speechRate: 250, volume: "quiet", monotony: "expressive", numFillers: 5, fillers: ["ну", "вот"], emotion: "neutral",
                       clarity: 86, clarityLevel: "medium")
        return SpeechResult(id: 1, text: monotone ? "" : "Ну, вот, сегодня я расскажу о нашем приложении.", duration: 60, feedback: feedback, recommendation: Recommendation(
            title: "У вас здорово получается!", description: "В следующий раз попробуйте **увеличить громкость** вашего голоса."),
            segments: monotone ? [] : [
                Segment(text: "Ну, вот, сегодня я расскажу", rate: 212, rateStatus: "fast", emotion: "neutral",
                        parts: [TextPart("Ну", filler: true), TextPart(", "), TextPart("вот", filler: true), TextPart(", сегодня я расскажу")]),
                Segment(text: "о нашем приложении.", rate: 140, rateStatus: "normal", emotion: "sadness",
                        parts: [TextPart("о нашем "), TextPart("приложении", unclear: true), TextPart(".")], clarity: 62, clarityLevel: "unclear"),
            ],
            content: monotone ? nil : SpeechContent(
                mainIdea: "Сегодня я расскажу о нашем приложении.", keywords: ["приложение", "речь"],
                structure: .init(level: "partial", summary: "Вступление есть; мало связок между мыслями; заключения нет: выступление обрывается без вывода.")))
    }

    func profile() async throws -> Profile {
        try maybeFail()
        let tempo = [(2, 118), (4, 126), (6, 125), (8, 133), (10, 142)].map { TempoPoint(date: String(format: "2026-10-%02dT10:00:00", $0.0), rate: $0.1) }
        return Profile(user: .init(name: "Эдна Юсупова"), count: 12, minutes: 86, streak: 4, tempo: tempo, rateSlow: 90, rateFast: 140,
                       recent: try await trainings())
    }

    func trainings() async throws -> [TrainingBrief] {
        try maybeFail()
        return [TrainingBrief(id: 7, title: "Подготовка к выступлению", date: "2026-10-10T10:00:00", duration: 240),
                TrainingBrief(id: 6, title: "Самопрезентация", date: "2026-10-08T10:00:00", duration: 180)]
    }

    func speech(id: Int) async throws -> SpeechResult {
        try await uploadSpeech(file: URL(fileURLWithPath: "/dev/null"), slides: nil, marks: [])
    }

    func stats() async throws -> Stats {
        try maybeFail()
        let thresholds: [String: Double] = ["rate_slow": 90, "rate_fast": 140, "fillers_max": 4, "volume_quiet_db": -30,
                                           "volume_loud_db": -12, "monotony_min_semitones": 2, "clarity_unclear": 75, "clarity_clear": 88]
        guard withStats else { return Stats(points: [], thresholds: thresholds) }
        let points = [(1, 205.0, 10), (2, 196.0, 5), (3, 155.0, 2)].map { day, rate, fillers in
            StatPoint(date: String(format: "2023-05-%02dT10:00:00", day), speechRate: rate, numFillers: fillers,
                      volumeDb: -20 - Double(day), pitchVariability: 2 + Double(day) / 10, clarity: 80 + Double(day))
        }
        return Stats(points: points, thresholds: thresholds)
    }
}

/// Диктофон без микрофона: длительность записи задаёт тест.
final class FakeRecorder: Recorder {
    private(set) var state: RecorderState = .idle
    private(set) var elapsed: TimeInterval = 0
    private let duration: TimeInterval
    private let failOnStart: Bool
    private var file: URL?

    init(environment: [String: String]) {
        duration = environment["FAKE_SHORT"] == "1" ? 1.5 : 140
        failOnStart = environment["FAKE_MIC_FAIL"] == "1"
    }

    func start(to url: URL) throws {
        if failOnStart { throw RecorderError() }
        try Data(count: 64).write(to: url)
        file = url
        elapsed = duration
        state = .recording
    }

    func pause() { if state == .recording { state = .paused } }
    func resume() { if state == .paused { state = .recording } }

    func stop() -> URL? {
        if state == .recording || state == .paused { state = .stopped }
        return file
    }

    func discard() {
        if let file { try? FileManager.default.removeItem(at: file) }
        file = nil
        elapsed = 0
        state = .idle
    }
}

extension Services {
    static func uiTesting(environment: [String: String]) -> Services {
        let defaults = UserDefaults(suiteName: "ui-testing")!
        defaults.removePersistentDomain(forName: "ui-testing")
        let session = SessionStore(defaults: defaults, service: "ru.itmo.talkmate.ui-testing")
        session.clear()
        if environment["FAKE_LOGGED_IN"] == "1" {
            session.save(AuthResult(token: "token", user: User(id: 1, name: "Эдна", email: "edna@itmo.ru")))
        }
        return Services(
            session: session,
            api: FakeApi(environment: environment),
            makeRecorder: { FakeRecorder(environment: environment) },
            requestMicrophone: { environment["FAKE_MIC_DENIED"] != "1" }
        )
    }
}
#endif
