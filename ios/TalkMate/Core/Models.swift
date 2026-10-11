import Foundation

struct User: Codable, Equatable {
    let id: Int
    let name: String
    let email: String
    var role: String = "user"

    private enum CodingKeys: String, CodingKey { case id, name, email, role }

    init(id: Int, name: String, email: String, role: String = "user") {
        self.id = id
        self.name = name
        self.email = email
        self.role = role
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(Int.self, forKey: .id)
        name = try c.decode(String.self, forKey: .name)
        email = try c.decode(String.self, forKey: .email)
        role = try c.decodeIfPresent(String.self, forKey: .role) ?? "user"
    }
}

struct AuthResult: Codable, Equatable {
    let token: String
    let user: User
}

struct RegisterRequest: Equatable {
    var name: String
    var email: String
    var password: String
    var phone: String?
    var birthDate: String?
    var gender: String?

    /// Тело запроса. Пустые необязательные поля не отправляются.
    var json: [String: Any] {
        var body: [String: Any] = ["name": name, "email": email, "password": password]
        if let phone, !phone.trimmingCharacters(in: .whitespaces).isEmpty { body["phone"] = phone }
        if let birthDate, !birthDate.isEmpty { body["birth_date"] = birthDate }
        if let gender { body["gender"] = gender }
        return body
    }
}

struct ArticleSummary: Codable, Hashable, Identifiable {
    let id: Int
    let title: String
}

struct Article: Codable, Equatable {
    let id: Int
    let title: String
    let content: String
}

struct Feedback: Codable, Hashable {
    let speechRate: Double
    let volume: String
    var volumeDb: Double = 0
    let monotony: String
    var pitchVariability: Double = 0
    let numFillers: Int
    var fillers: [String] = []
    let emotion: String?
    /// Чёткость речи в процентах и её уровень: clear, medium, unclear. Пусто, если сервер её не определил.
    var clarity: Double?
    var clarityLevel: String?

    private enum CodingKeys: String, CodingKey {
        case speechRate = "speech_rate", volume, volumeDb = "volume_db", monotony
        case pitchVariability = "pitch_variability", numFillers = "num_fillers", fillers, emotion
        case clarity, clarityLevel = "clarity_level"
    }

    init(speechRate: Double, volume: String, volumeDb: Double = 0, monotony: String, pitchVariability: Double = 0,
         numFillers: Int, fillers: [String] = [], emotion: String?, clarity: Double? = nil, clarityLevel: String? = nil) {
        self.clarity = clarity
        self.clarityLevel = clarityLevel
        self.speechRate = speechRate
        self.volume = volume
        self.volumeDb = volumeDb
        self.monotony = monotony
        self.pitchVariability = pitchVariability
        self.numFillers = numFillers
        self.fillers = fillers
        self.emotion = emotion
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        speechRate = try c.decode(Double.self, forKey: .speechRate)
        volume = try c.decode(String.self, forKey: .volume)
        volumeDb = try c.decodeIfPresent(Double.self, forKey: .volumeDb) ?? 0
        monotony = try c.decode(String.self, forKey: .monotony)
        pitchVariability = try c.decodeIfPresent(Double.self, forKey: .pitchVariability) ?? 0
        numFillers = try c.decode(Int.self, forKey: .numFillers)
        fillers = try c.decodeIfPresent([String].self, forKey: .fillers) ?? []
        emotion = try c.decodeIfPresent(String.self, forKey: .emotion)
        clarity = try c.decodeIfPresent(Double.self, forKey: .clarity)
        clarityLevel = try c.decodeIfPresent(String.self, forKey: .clarityLevel)
    }
}

struct Recommendation: Codable, Hashable {
    let title: String
    let description: String
}

/// Кусок текста фразы: обычный или слово-заполнитель.
struct TextPart: Codable, Hashable {
    let text: String
    var filler: Bool = false
    /// Слово прозвучало неразборчиво.
    var unclear: Bool = false

    private enum CodingKeys: String, CodingKey { case text, filler, unclear }

    init(_ text: String, filler: Bool = false, unclear: Bool = false) {
        self.text = text
        self.filler = filler
        self.unclear = unclear
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        text = try c.decode(String.self, forKey: .text)
        filler = try c.decodeIfPresent(Bool.self, forKey: .filler) ?? false
        unclear = try c.decodeIfPresent(Bool.self, forKey: .unclear) ?? false
    }
}

/// Фраза расшифровки со своей оценкой темпа и окраски.
struct Segment: Codable, Hashable {
    let text: String
    let rate: Double
    let rateStatus: String
    let emotion: String?
    var parts: [TextPart] = []
    var clarity: Double?
    var clarityLevel: String?

    private enum CodingKeys: String, CodingKey {
        case text, rate, rateStatus = "rate_status", emotion, parts, clarity, clarityLevel = "clarity_level"
    }

    init(text: String, rate: Double, rateStatus: String, emotion: String?, parts: [TextPart], clarity: Double? = nil, clarityLevel: String? = nil) {
        self.clarity = clarity
        self.clarityLevel = clarityLevel
        self.text = text
        self.rate = rate
        self.rateStatus = rateStatus
        self.emotion = emotion
        self.parts = parts
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        text = try c.decodeIfPresent(String.self, forKey: .text) ?? ""
        rate = try c.decodeIfPresent(Double.self, forKey: .rate) ?? 0
        rateStatus = try c.decodeIfPresent(String.self, forKey: .rateStatus) ?? "normal"
        emotion = try c.decodeIfPresent(String.self, forKey: .emotion)
        parts = try c.decodeIfPresent([TextPart].self, forKey: .parts) ?? []
        clarity = try c.decodeIfPresent(Double.self, forKey: .clarity)
        clarityLevel = try c.decodeIfPresent(String.self, forKey: .clarityLevel)
    }
}

/// Содержание выступления: основная мысль (цитата из речи), ключевые слова и оценка структуры.
struct SpeechContent: Codable, Hashable {
    struct Structure: Codable, Hashable {
        var level: String?
        var summary: String?
    }

    var mainIdea: String?
    var keywords: [String]?
    var structure: Structure?

    private enum CodingKeys: String, CodingKey { case mainIdea = "main_idea", keywords, structure }
}

/// Отметка приложения: с этой секунды записи на экране такой-то слайд.
struct SlideMark: Equatable {
    let page: Int
    let start: Double
}

/// Один слайд презентации в сравнении с речью.
struct SlideItem: Codable, Hashable {
    var page: Int = 0
    var title: String?
    var seconds: Int?
    var coverage: Int?
    var reading: Int?
    var missed: [String]?
    var status: String?
    var dense: Bool?
    var smallText: Bool?

    private enum CodingKeys: String, CodingKey { case page, title, seconds, coverage, reading, missed, status, dense, smallText = "small_text" }
}

/// Сопоставление речи с презентацией. При ошибке чтения файла заполнено только error.
struct SlidesReport: Codable, Hashable {
    var pages: Int?
    var coverage: Int?
    var reading: Int?
    var items: [SlideItem]?
    var notes: [String]?
    var error: String?
    /// Время на слайд взято из переключений в приложении, а не оценено по словам.
    var timed: Bool?
}

struct SpeechResult: Codable, Hashable {
    let id: Int
    var text: String = ""
    var duration: Double = 0
    let feedback: Feedback
    let recommendation: Recommendation?
    var segments: [Segment] = []
    var content: SpeechContent?
    var slides: SlidesReport?

    private enum CodingKeys: String, CodingKey { case id, text, duration, feedback, recommendation, segments, content, slides }

    init(id: Int, text: String = "", duration: Double = 0, feedback: Feedback, recommendation: Recommendation?, segments: [Segment] = [],
         content: SpeechContent? = nil, slides: SlidesReport? = nil) {
        self.content = content
        self.slides = slides
        self.id = id
        self.text = text
        self.duration = duration
        self.feedback = feedback
        self.recommendation = recommendation
        self.segments = segments
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(Int.self, forKey: .id)
        text = try c.decodeIfPresent(String.self, forKey: .text) ?? ""
        duration = try c.decodeIfPresent(Double.self, forKey: .duration) ?? 0
        feedback = try c.decode(Feedback.self, forKey: .feedback)
        recommendation = try c.decodeIfPresent(Recommendation.self, forKey: .recommendation)
        segments = try c.decodeIfPresent([Segment].self, forKey: .segments) ?? []
        content = try c.decodeIfPresent(SpeechContent.self, forKey: .content)
        slides = try c.decodeIfPresent(SlidesReport.self, forKey: .slides)
    }
}

/// Тренировка в списке: только то, что нужно строке.
struct TrainingBrief: Codable, Hashable, Identifiable {
    let id: Int
    var title: String = ""
    var date: String = ""
    var duration: Int = 0
}

struct TempoPoint: Codable, Hashable {
    var date: String = ""
    var rate: Int = 0
}

/// Личный кабинет: счётчики и темп последних тренировок.
struct Profile: Codable, Hashable {
    struct Owner: Codable, Hashable { var name: String? }

    var user: Owner?
    var count: Int = 0
    var minutes: Int = 0
    var streak: Int = 0
    var tempo: [TempoPoint] = []
    var rateSlow: Double = 90
    var rateFast: Double = 140
    var recent: [TrainingBrief] = []

    private enum CodingKeys: String, CodingKey { case user, count, minutes, streak, tempo, rateSlow = "rate_slow", rateFast = "rate_fast", recent }
}

struct StatPoint: Codable, Equatable {
    let date: String
    let speechRate: Double
    let numFillers: Int
    var volumeDb: Double = 0
    var pitchVariability: Double = 0
    var clarity: Double?

    private enum CodingKeys: String, CodingKey {
        case date, speechRate = "speech_rate", numFillers = "num_fillers", volumeDb = "volume_db", pitchVariability = "pitch_variability", clarity
    }

    init(date: String, speechRate: Double, numFillers: Int, volumeDb: Double = 0, pitchVariability: Double = 0, clarity: Double? = nil) {
        self.clarity = clarity
        self.date = date
        self.speechRate = speechRate
        self.numFillers = numFillers
        self.volumeDb = volumeDb
        self.pitchVariability = pitchVariability
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        date = try c.decode(String.self, forKey: .date)
        speechRate = try c.decode(Double.self, forKey: .speechRate)
        numFillers = try c.decode(Int.self, forKey: .numFillers)
        volumeDb = try c.decodeIfPresent(Double.self, forKey: .volumeDb) ?? 0
        pitchVariability = try c.decodeIfPresent(Double.self, forKey: .pitchVariability) ?? 0
        clarity = try c.decodeIfPresent(Double.self, forKey: .clarity)
    }
}

struct Stats: Codable, Equatable {
    let points: [StatPoint]
    var thresholds: [String: Double] = [:]

    private enum CodingKeys: String, CodingKey { case points, thresholds }

    init(points: [StatPoint], thresholds: [String: Double] = [:]) {
        self.points = points
        self.thresholds = thresholds
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        points = try c.decode([StatPoint].self, forKey: .points)
        thresholds = try c.decodeIfPresent([String: Double].self, forKey: .thresholds) ?? [:]
    }
}
