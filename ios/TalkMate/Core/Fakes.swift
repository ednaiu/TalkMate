#if DEBUG
import Foundation
import UIKit

/// Сервер в памяти для UI-тестов. Включается аргументом запуска -uiTesting, поведение задают переменные окружения.
final class FakeApi: Api {
    private var failures: [ApiError]
    private var accounts: [String: (password: String, name: String)] = ["edna@itmo.ru": ("secret1", L("Эдна", "Edna"))]
    private let withStats: Bool
    private let withSlides: Bool
    private let monotone: Bool

    init(environment: [String: String]) {
        failures = (environment["FAKE_FAIL"] ?? "").split(separator: ",").compactMap { kind in
            switch kind {
            case "network": return ApiError.network
            case "server": return ApiError(kind: .server, message: L("Сервис распознавания речи недоступен", "The speech recognition service is unavailable"))
            case "unauthorized": return ApiError(kind: .unauthorized, message: "Сессия истекла, войдите снова")
            default: return nil
            }
        }
        withStats = environment["FAKE_STATS"] == "1"
        withSlides = environment["FAKE_SLIDES"] == "1"
        monotone = environment["FAKE_MONOTONE"] == "1"
    }

    static let articleList = [
        Article(id: 1, title: L("Жестикуляция и движение", "Gestures and movement"), content: L("Жестикуляция состоит из пяти основных жестов: **толкание, вытягивание, подъём, бросание и разрывание.** Каждое из них можно выполнить в шести направлениях.", "There are five basic gestures: **pushing, pulling, lifting, throwing and separating.** Each can be performed in six directions.")),
        Article(id: 2, title: L("Подготовка на площадке", "Preparing at the venue"), content: L("Приходите в зал за полчаса до начала.", "Arrive at the venue half an hour before your talk.")),
        Article(id: 3, title: L("Использование презентаций", "Using slides"), content: L("Одна мысль на слайд.", "One idea per slide.")),
        Article(id: 4, title: L("Разогрев", "Warm-up"), content: L("Голос работает как мышца.", "Your voice works like a muscle.")),
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
            : Feedback(speechRate: 250, volume: "quiet", monotony: "expressive", numFillers: 5, fillers: [L("ну", "um"), L("вот", "you know")], emotion: "neutral",
                       clarity: 86, clarityLevel: "medium")
        return SpeechResult(id: 1, text: monotone ? "" : L("Ну, вот, сегодня я расскажу о нашем приложении.", "Um, you know, today I will talk about our app."), duration: 60, feedback: feedback, recommendation: Recommendation(
            title: L("У вас здорово получается!", "You are doing well!"), description: L("В следующий раз попробуйте **увеличить громкость** вашего голоса.", "Next time, try **increasing your volume**.")),
            segments: monotone ? [] : [
                Segment(text: L("Ну, вот, сегодня я расскажу", "Um, you know, today I will talk"), rate: 212, rateStatus: "fast", emotion: "neutral",
                        parts: [TextPart(L("Ну", "Um"), filler: true), TextPart(", "), TextPart(L("вот", "you know"), filler: true), TextPart(L(", сегодня я расскажу", ", today I will talk"))]),
                Segment(text: L("о нашем приложении.", "about our app."), rate: 140, rateStatus: "normal", emotion: "sadness",
                        parts: [TextPart(L("о нашем ", "about our ")), TextPart(L("приложении", "app"), unclear: true), TextPart(".")], clarity: 62, clarityLevel: "unclear"),
            ],
            content: monotone ? nil : SpeechContent(
                mainIdea: L("Сегодня я расскажу о нашем приложении.", "Today I will talk about our app."), keywords: [L("приложение", "app"), L("речь", "speech")],
                structure: .init(level: "partial", summary: L("Вступление есть; мало связок между мыслями; заключения нет: выступление обрывается без вывода.", "There is an introduction, but few links between ideas. Add a conclusion to bring the talk to a close."))),
            slides: withSlides ? SlidesReport(pages: 2, coverage: 65, reading: 20,
                items: [SlideItem(page: 1, title: L("О чём выступление", "The main idea"), seconds: 35, coverage: 80, reading: 15,
                                  missed: [L("Пример", "Example")], status: "covered"),
                        SlideItem(page: 2, title: L("Следующий шаг", "The next step"), seconds: 25, coverage: 50, reading: 25,
                                  missed: [L("Вывод", "Conclusion")], status: "partly")],
                notes: [L("Добавьте короткий пример к основной мысли.", "Add a short example to support the main idea.")], timed: true) : nil)
    }

    func profile() async throws -> Profile {
        try maybeFail()
        let tempo = [(2, 118), (4, 126), (6, 125), (8, 133), (10, 142)].map { TempoPoint(date: String(format: "2026-10-%02dT10:00:00", $0.0), rate: $0.1) }
        return Profile(user: .init(name: L("Эдна Юсупова", "Edna Yusupova")), count: 12, minutes: 86, streak: 4, tempo: tempo, rateSlow: 90, rateFast: 140,
                       recent: try await trainings())
    }

    func trainings() async throws -> [TrainingBrief] {
        try maybeFail()
        return [TrainingBrief(id: 7, title: L("Подготовка к выступлению", "Preparing for a talk"), date: "2026-10-10T10:00:00", duration: 240),
                TrainingBrief(id: 6, title: L("Самопрезентация", "Introducing yourself"), date: "2026-10-08T10:00:00", duration: 180)]
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
            session.save(AuthResult(token: "token", user: User(id: 1, name: L("Эдна", "Edna"), email: "edna@itmo.ru")))
        }
        return Services(
            session: session,
            api: FakeApi(environment: environment),
            makeRecorder: { FakeRecorder(environment: environment) },
            requestMicrophone: { environment["FAKE_MIC_DENIED"] != "1" }
        )
    }
}
/// Только тестовые данные для экспорта существующего PDF-просмотрщика.
@MainActor
enum ScreenshotFixtures {
    static func presentation() -> URL? {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(L("Демо-презентация.pdf", "Demo-presentation.pdf"))
        let renderer = UIGraphicsPDFRenderer(bounds: CGRect(x: 0, y: 0, width: 960, height: 540))
        do {
            try renderer.writePDF(to: url) { context in
                for (index, title) in [L("О чём выступление", "The main idea"), L("Следующий шаг", "The next step")].enumerated() {
                    context.beginPage()
                    UIColor.white.setFill()
                    context.cgContext.fill(CGRect(x: 0, y: 0, width: 960, height: 540))
                    (title as NSString).draw(at: CGPoint(x: 64, y: 90), withAttributes: [
                        .font: UIFont.systemFont(ofSize: 46, weight: .semibold), .foregroundColor: UIColor.black])
                    (L("Демонстрационная презентация • Слайд \(index + 1)", "Demo presentation • Slide \(index + 1)") as NSString).draw(at: CGPoint(x: 64, y: 190), withAttributes: [
                        .font: UIFont.systemFont(ofSize: 26), .foregroundColor: UIColor.darkGray])
                    UIColor(red: 0.27, green: 0.39, blue: 0.84, alpha: 1).setFill()
                    context.cgContext.fill(CGRect(x: 64, y: 290, width: 600, height: 12))
                }
            }
            return url
        } catch { return nil }
    }
}
#endif
