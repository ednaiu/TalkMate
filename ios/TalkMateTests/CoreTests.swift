import XCTest
@testable import TalkMate

final class FormattersTests: XCTestCase {
    func testRateMatchesMockup() {
        XCTAssertEqual(Formatters.rate(250), "250 сл/мин")
        XCTAssertEqual(Formatters.rate(249.6), "250 сл/мин")
    }

    func testVolumeAndEmotionLabels() {
        XCTAssertEqual(["quiet", "normal", "loud"].map(Formatters.volume), ["тихая", "нормальная", "громкая"])
        let expected = ["anger": "злость", "disgust": "отвращение", "fear": "страх", "happiness": "счастье",
                        "enthusiasm": "интерес", "sadness": "грусть", "neutral": "нейтральная"]
        for (label, text) in expected { XCTAssertEqual(Formatters.emotion(label), text) }
        XCTAssertEqual(Formatters.emotion(nil), "не определена")
        XCTAssertEqual(Formatters.emotion("surprise"), "не определена")
    }

    func testFillersUseRussianPlurals() {
        let cases = [0: "0 слов", 1: "1 слово", 3: "3 слова", 5: "5 слов", 11: "11 слов", 14: "14 слов",
                     21: "21 слово", 22: "22 слова", 111: "111 слов"]
        for (count, text) in cases { XCTAssertEqual(Formatters.fillers(count), text) }
    }

    func testMonotony() {
        XCTAssertEqual(Formatters.monotonyDescription("monotone"), "монотонная")
        XCTAssertEqual(Formatters.monotonyDescription("expressive"), "выразительная")
    }

    func testTimer() {
        XCTAssertEqual(Formatters.timer(0), "00:00.000")
        XCTAssertEqual(Formatters.timer(0.999), "00:00.999")
        XCTAssertEqual(Formatters.timer(7.35), "00:07.350")
        XCTAssertEqual(Formatters.timer(59), "00:59.000")
        XCTAssertEqual(Formatters.timer(140), "02:20.000")
        XCTAssertEqual(Formatters.timer(3665.042), "61:05.042")
        XCTAssertEqual(["good", "partial", "weak", "short"].map(Formatters.structure), ["хорошая", "частичная", "слабая", "не оценена"])
        XCTAssertEqual(Formatters.structure(nil), "не оценена")
    }

    func testBirthDateConversion() {
        XCTAssertEqual(Formatters.birthDateToISO("17.05.2001"), "2001-05-17")
        XCTAssertEqual(Formatters.birthDateToISO(" 7.5.2001 "), "2001-05-07")
        XCTAssertEqual(Formatters.birthDateToISO("29.02.2000"), "2000-02-29")
        for bad in ["29.02.2001", "31.04.2001", "17.13.2001", "2001-05-17", "завтра", "1.1.99", ""] {
            XCTAssertNil(Formatters.birthDateToISO(bad), bad)
        }
    }

    func testShortDateAndNumbers() {
        XCTAssertEqual(Formatters.shortDate("2023-05-07T10:11:12"), "07.05")
        XCTAssertEqual(Formatters.shortDate("мусор"), "мусор")
        XCTAssertEqual(Formatters.number(154.6, decimals: 0), "155")
        XCTAssertEqual(Formatters.number(-17.66, decimals: 1), "-17,7")
    }
}

final class ValidationTests: XCTestCase {
    func testNameEmailPassword() {
        XCTAssertNil(Validation.name("Эдна"))
        XCTAssertEqual(Validation.name("   "), "Введите имя")
        XCTAssertNil(Validation.email("johndoe@example.com"))
        XCTAssertNil(Validation.email("  edna@itmo.ru "))
        XCTAssertEqual(Validation.email(""), "Введите email")
        for bad in ["johndoe", "john@doe", "@example.com", "john doe@example.com"] {
            XCTAssertEqual(Validation.email(bad), "Введите корректный email", bad)
        }
        XCTAssertNil(Validation.password("123456"))
        XCTAssertEqual(Validation.password(""), "Введите пароль")
        XCTAssertNotNil(Validation.password("12345"))
    }

    func testCodeBirthDateAndServer() {
        XCTAssertNil(Validation.code("123456"))
        XCTAssertNil(Validation.code(" 000001 "))
        for bad in ["", "12345", "1234567", "12a456"] { XCTAssertNotNil(Validation.code(bad), bad) }
        XCTAssertNil(Validation.birthDate(""))
        XCTAssertNil(Validation.birthDate("17.05.2001"))
        XCTAssertNotNil(Validation.birthDate("17/05/2001"))
        XCTAssertNil(Validation.serverURL("http://localhost:5050"))
        XCTAssertNil(Validation.serverURL("https://talkmate.example.com/api"))
        for bad in ["localhost:5050", "ftp://host", ""] { XCTAssertNotNil(Validation.serverURL(bad), bad) }
    }
}

final class MarkupTests: XCTestCase {
    func testParse() {
        XCTAssertEqual(Markup.parse("просто текст"), [.init(text: "просто текст", bold: false)])
        XCTAssertEqual(Markup.parse("попробуйте **увеличить громкость** голоса"),
                       [.init(text: "попробуйте ", bold: false), .init(text: "увеличить громкость", bold: true), .init(text: " голоса", bold: false)])
        XCTAssertEqual(Markup.parse("**раз** и **два**"), [.init(text: "раз", bold: true), .init(text: " и ", bold: false), .init(text: "два", bold: true)])
        XCTAssertEqual(Markup.parse("цена 2**3 рубля"), [.init(text: "цена 2**3 рубля", bold: false)])
        XCTAssertEqual(Markup.parse(""), [])
        XCTAssertEqual(Markup.plain("а **б** в"), "а б в")
    }
}

final class TranscriptMarksTests: XCTestCase {
    private func segment(_ status: String = "normal", _ emotion: String? = "neutral", rate: Double = 150, fillers: Int = 0) -> Segment {
        Segment(text: "текст", rate: rate, rateStatus: status, emotion: emotion,
                parts: Array(repeating: TextPart("ну", filler: true), count: fillers) + [TextPart(" текст")])
    }

    func testMarks() {
        XCTAssertTrue(TranscriptMarks.marks(segment()).isEmpty)
        XCTAssertTrue(TranscriptMarks.marks(segment("normal", nil)).isEmpty)
        XCTAssertEqual(TranscriptMarks.marks(segment("fast", rate: 212)), [.init(text: "быстро, 212 сл/мин", kind: .tempo)])
        XCTAssertEqual(TranscriptMarks.marks(segment("slow", rate: 80)), [.init(text: "медленно, 80 сл/мин", kind: .tempo)])
        XCTAssertEqual(TranscriptMarks.marks(segment("normal", "happiness")), [.init(text: "счастье", kind: .emotion)])
        XCTAssertEqual(TranscriptMarks.marks(segment("fast", "anger", rate: 200)),
                       [.init(text: "быстро, 200 сл/мин", kind: .tempo), .init(text: "злость", kind: .negativeEmotion)])
    }

    func testUnclearSegment() {
        let unclear = Segment(text: "текст", rate: 150, rateStatus: "normal", emotion: "neutral",
                              parts: [TextPart("текст", unclear: true)], clarity: 62, clarityLevel: "unclear")
        XCTAssertEqual(TranscriptMarks.marks(unclear), [.init(text: "невнятно, 62%", kind: .negativeEmotion)])
        XCTAssertEqual(TranscriptMarks.summary([unclear, segment()]), "Невнятная фраза: 1")
        XCTAssertEqual(Formatters.clarity(95, "clear"), "чёткая, 95%")
        XCTAssertEqual(Formatters.clarity(82, "medium"), "средняя, 82%")
        XCTAssertEqual(Formatters.clarity(60, "unclear"), "невнятная, 60%")
        XCTAssertEqual(Formatters.clarity(nil, nil), "не определена")
    }

    func testClarityIsDecoded() throws {
        let json = #"""
        {"id":3,"feedback":{"speech_rate":120,"volume":"normal","monotony":"expressive","num_fillers":0,"emotion":null,"clarity":86,"clarity_level":"medium"},
         "recommendation":null,
         "segments":[{"text":"текст","rate":120,"rate_status":"normal","emotion":null,"clarity":62,"clarity_level":"unclear",
                      "parts":[{"text":"текст","filler":false,"unclear":true}]}]}
        """#
        let speech = try JSONDecoder().decode(SpeechResult.self, from: Data(json.utf8))
        XCTAssertEqual(speech.feedback.clarity, 86)
        XCTAssertEqual(speech.feedback.clarityLevel, "medium")
        XCTAssertEqual(speech.segments[0].clarityLevel, "unclear")
        XCTAssertTrue(speech.segments[0].parts[0].unclear)
        let stats = try JSONDecoder().decode(Stats.self, from: Data(#"{"points":[{"date":"2026-10-10","speech_rate":120,"num_fillers":0,"clarity":91},{"date":"2026-10-09","speech_rate":120,"num_fillers":0,"clarity":null}]}"#.utf8))
        XCTAssertEqual(stats.points.map(\.clarity), [91, nil])
    }

    func testContentIsDecoded() throws {
        let json = #"""
        {"id":3,"feedback":{"speech_rate":120,"volume":"normal","monotony":"expressive","num_fillers":0,"emotion":null},"recommendation":null,
         "content":{"main_idea":"Приложение помогает тренировать выступления.","keywords":["приложение","выступления"],
                    "structure":{"level":"good","intro":true,"links":4,"conclusion":true,"summary":"Вступление есть; логических связок: 4; заключение есть."}}}
        """#
        let content = try XCTUnwrap(JSONDecoder().decode(SpeechResult.self, from: Data(json.utf8)).content)
        XCTAssertEqual(content.mainIdea, "Приложение помогает тренировать выступления.")
        XCTAssertEqual(content.keywords, ["приложение", "выступления"])
        XCTAssertEqual(content.structure?.level, "good")
        let short = #"{"id":3,"feedback":{"speech_rate":120,"volume":"normal","monotony":"expressive","num_fillers":0,"emotion":null},"recommendation":null,"content":{"main_idea":null,"keywords":[],"structure":{"level":"short","intro":null,"links":null,"conclusion":null,"summary":"Запись слишком короткая"}}}"#
        XCTAssertNil(try JSONDecoder().decode(SpeechResult.self, from: Data(short.utf8)).content?.mainIdea)
        let old = #"{"id":3,"feedback":{"speech_rate":120,"volume":"normal","monotony":"expressive","num_fillers":0,"emotion":null},"recommendation":null}"#
        XCTAssertNil(try JSONDecoder().decode(SpeechResult.self, from: Data(old.utf8)).content)
    }

    func testSummary() {
        XCTAssertEqual(TranscriptMarks.summary([segment(), segment("normal", "happiness")]), "Замечаний по фразам нет")
        XCTAssertEqual(TranscriptMarks.summary([segment("fast", fillers: 2), segment("slow", "fear", fillers: 1), segment()]),
                       "Заполнителей: 3; фразы с темпом вне нормы: 2; фраза с отрицательной окраской: 1")
    }

    func testSegmentsAreDecoded() throws {
        let json = #"""
        {"id":1,"text":"Ну, вот.","feedback":{"speech_rate":150,"volume":"normal","monotony":"expressive","num_fillers":2,"emotion":"neutral"},"recommendation":null,
         "segments":[{"start":0.0,"end":4.1,"text":"Ну, вот.","rate":212,"rate_status":"fast","emotion":null,
                      "parts":[{"text":"Ну","filler":true},{"text":", ","filler":false},{"text":"вот","filler":true},{"text":".","filler":false}]}]}
        """#
        let speech = try JSONDecoder().decode(SpeechResult.self, from: Data(json.utf8))
        XCTAssertEqual(speech.segments.count, 1)
        XCTAssertEqual(speech.segments[0].rateStatus, "fast")
        XCTAssertNil(speech.segments[0].emotion)
        XCTAssertEqual(speech.segments[0].parts.filter(\.filler).map(\.text), ["Ну", "вот"])
        XCTAssertEqual(speech.segments[0].parts.map(\.text).joined(), "Ну, вот.")
    }
}

final class ModelsTests: XCTestCase {
    private func decode<T: Decodable>(_ json: String) throws -> T { try JSONDecoder().decode(T.self, from: Data(json.utf8)) }

    func testAuthAndSpeech() throws {
        let auth: AuthResult = try decode(#"{"token":"abc","user":{"id":7,"name":"Эдна","email":"e@itmo.ru","role":"user","phone":null}}"#)
        XCTAssertEqual(auth.token, "abc")
        XCTAssertEqual(auth.user, User(id: 7, name: "Эдна", email: "e@itmo.ru"))

        let speech: SpeechResult = try decode(#"""
        {"id":3,"text":"ну вот","duration":12.5,"created_at":"2026-10-10T10:00:00",
         "feedback":{"speech_rate":250,"volume":"quiet","volume_db":-34.2,"monotony":"monotone","pitch_variability":1.1,
                     "num_fillers":5,"fillers":["ну","вот"],"emotion":"neutral"},
         "recommendation":{"id":1,"speech_id":3,"title":"У вас здорово получается!","description":"**увеличить громкость**"}}
        """#)
        XCTAssertEqual(speech.feedback.speechRate, 250)
        XCTAssertEqual(speech.feedback.fillers, ["ну", "вот"])
        XCTAssertEqual(speech.feedback.emotion, "neutral")
        XCTAssertEqual(speech.recommendation?.title, "У вас здорово получается!")
    }

    func testSpeechWithoutEmotionAndRecommendation() throws {
        let speech: SpeechResult = try decode(#"{"id":3,"feedback":{"speech_rate":120,"volume":"normal","monotony":"expressive","num_fillers":0,"emotion":null},"recommendation":null}"#)
        XCTAssertNil(speech.feedback.emotion)
        XCTAssertTrue(speech.feedback.fillers.isEmpty)
        XCTAssertNil(speech.recommendation)
    }

    func testStatsAndArticles() throws {
        let stats: Stats = try decode(#"{"count":2,"thresholds":{"rate_slow":120.0,"rate_fast":180.0},"points":[{"speech_id":1,"date":"2023-05-01T10:00:00","speech_rate":205,"num_fillers":10,"volume_db":-20.5,"pitch_variability":2.4,"emotion":null}]}"#)
        XCTAssertEqual(stats.points.map(\.speechRate), [205])
        XCTAssertEqual(stats.thresholds["rate_slow"], 120)
        let empty: Stats = try decode(#"{"points":[]}"#)
        XCTAssertTrue(empty.points.isEmpty && empty.thresholds.isEmpty)
        let list: [ArticleSummary] = try decode(#"[{"id":1,"title":"Разогрев","created_at":"x"}]"#)
        XCTAssertEqual(list.map(\.title), ["Разогрев"])
    }

    func testRegisterBodySkipsEmptyOptionalFields() {
        let minimal = RegisterRequest(name: "John Doe", email: "johndoe@example.com", password: "password", phone: " ")
        XCTAssertEqual(Set(minimal.json.keys), ["name", "email", "password"])
        let full = RegisterRequest(name: "Эдна", email: "e@itmo.ru", password: "password", phone: "+7999", birthDate: "2001-05-17", gender: "female")
        XCTAssertEqual(full.json["birth_date"] as? String, "2001-05-17")
        XCTAssertEqual(full.json["gender"] as? String, "female")
    }

    func testErrorsAreClassified() {
        func error(_ status: Int, _ body: String) -> ApiError { ApiError.from(status: status, body: Data(body.utf8)) }
        let wrong = error(401, #"{"error":"invalid_credentials","message":"Неверный email или пароль"}"#)
        XCTAssertEqual(wrong.kind, .rejected)
        XCTAssertEqual(wrong.message, "Неверный email или пароль")
        XCTAssertEqual(error(401, #"{"error":"unauthorized","message":"Сессия истекла"}"#).kind, .unauthorized)
        XCTAssertEqual(error(409, #"{"error":"email_taken","message":"Занято"}"#).kind, .rejected)
        XCTAssertEqual(error(422, #"{"error":"no_signal","message":"Микрофон не передал звук"}"#).code, "no_signal")
        XCTAssertEqual(error(503, #"{"error":"recognition_unavailable","message":"Недоступно"}"#).kind, .server)
        let html = error(502, "<html>Bad Gateway</html>")
        XCTAssertEqual(html.kind, .server)
        XCTAssertTrue(html.message.contains("502"))
    }
}

/// Перехватывает запросы URLSession, чтобы проверить клиент без сети.
final class StubProtocol: URLProtocol {
    static var handler: ((URLRequest, Data) -> (Int, Data))?
    static var failure: Error?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        if let failure = Self.failure {
            client?.urlProtocol(self, didFailWithError: failure)
            return
        }
        var body = request.httpBody ?? Data()
        if let stream = request.httpBodyStream {
            stream.open()
            var buffer = [UInt8](repeating: 0, count: 4096)
            while stream.hasBytesAvailable {
                let read = stream.read(&buffer, maxLength: buffer.count)
                if read <= 0 { break }
                body.append(buffer, count: read)
            }
        }
        let (status, data) = Self.handler!(request, body)
        client?.urlProtocol(self, didReceive: HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: data)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}

final class HttpApiTests: XCTestCase {
    private var token: String?

    private func makeApi(base: String = "http://server.test:5050/") -> HttpApi {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [StubProtocol.self]
        return HttpApi(baseURL: { base }, token: { [unowned self] in self.token }, session: URLSession(configuration: config))
    }

    override func setUp() {
        StubProtocol.handler = nil
        StubProtocol.failure = nil
        token = nil
    }

    func testLoginSendsJsonAndParsesAnswer() async throws {
        StubProtocol.handler = { request, body in
            XCTAssertEqual(request.url?.absoluteString, "http://server.test:5050/api/auth/login")
            XCTAssertEqual(request.httpMethod, "POST")
            XCTAssertNil(request.value(forHTTPHeaderField: "Authorization"))
            let json = try! JSONSerialization.jsonObject(with: body) as! [String: String]
            XCTAssertEqual(json, ["email": "e@itmo.ru", "password": "secret1"])
            return (200, Data(#"{"token":"t","user":{"id":1,"name":"Эдна","email":"e@itmo.ru"}}"#.utf8))
        }
        let result = try await makeApi().login(email: "e@itmo.ru", password: "secret1")
        XCTAssertEqual(result.user.name, "Эдна")
    }

    func testAuthorizedRequestCarriesToken() async throws {
        token = "abc"
        StubProtocol.handler = { request, _ in
            XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer abc")
            XCTAssertEqual(request.url?.path, "/api/articles/7")
            return (200, Data(#"{"id":7,"title":"Разогрев","content":"Текст"}"#.utf8))
        }
        let article = try await makeApi().article(id: 7)
        XCTAssertEqual(article.content, "Текст")
    }

    func testUploadSendsWavAsMultipart() async throws {
        let file = FileManager.default.temporaryDirectory.appendingPathComponent("upload-test.wav")
        try Data("RIFFdata".utf8).write(to: file)
        StubProtocol.handler = { request, body in
            XCTAssertEqual(request.url?.path, "/api/speeches")
            let type = request.value(forHTTPHeaderField: "Content-Type") ?? ""
            XCTAssertTrue(type.hasPrefix("multipart/form-data; boundary="))
            let text = String(decoding: body, as: UTF8.self)
            XCTAssertTrue(text.contains(#"name="audio"; filename="speech.wav""#))
            XCTAssertTrue(text.contains("RIFFdata"))
            XCTAssertTrue(text.hasSuffix("--\r\n"))
            return (201, Data(#"{"id":1,"feedback":{"speech_rate":150,"volume":"normal","monotony":"expressive","num_fillers":2,"emotion":"neutral"},"recommendation":null}"#.utf8))
        }
        let result = try await makeApi().uploadSpeech(file: file)
        XCTAssertEqual(result.feedback.numFillers, 2)
    }

    func testResetPasswordCalls() async throws {
        var paths: [String] = []
        StubProtocol.handler = { request, body in
            paths.append(request.url!.path)
            if request.url!.path.hasSuffix("/reset") {
                let json = try! JSONSerialization.jsonObject(with: body) as! [String: String]
                XCTAssertEqual(json, ["email": "e@itmo.ru", "code": "123456", "password": "newpass1"])
                return (200, Data(#"{"token":"t2","user":{"id":1,"name":"Эдна","email":"e@itmo.ru"}}"#.utf8))
            }
            return (200, Data(#"{"message":"ok"}"#.utf8))
        }
        let api = makeApi()
        try await api.requestPasswordReset(email: "e@itmo.ru")
        let result = try await api.resetPassword(email: "e@itmo.ru", code: "123456", newPassword: "newpass1")
        XCTAssertEqual(result.token, "t2")
        XCTAssertEqual(paths, ["/api/auth/forgot", "/api/auth/reset"])
    }

    func testErrorsAreMapped() async {
        StubProtocol.handler = { _, _ in (422, Data(#"{"error":"no_speech","message":"Не удалось распознать речь"}"#.utf8)) }
        do {
            _ = try await makeApi().stats()
            XCTFail("ожидалась ошибка")
        } catch let error as ApiError {
            XCTAssertEqual(error, ApiError(kind: .rejected, message: "Не удалось распознать речь", code: "no_speech"))
        } catch { XCTFail("\(error)") }

        StubProtocol.handler = { _, _ in (200, Data("не json".utf8)) }
        do { _ = try await makeApi().stats(); XCTFail("ожидалась ошибка") } catch { XCTAssertEqual(error as? ApiError, .badResponse) }

        StubProtocol.failure = URLError(.notConnectedToInternet)
        do { _ = try await makeApi().stats(); XCTFail("ожидалась ошибка") } catch { XCTAssertEqual(error as? ApiError, .network) }
    }
}

final class SessionStoreTests: XCTestCase {
    func testSaveReadAndClear() {
        let defaults = UserDefaults(suiteName: "session-tests")!
        defaults.removePersistentDomain(forName: "session-tests")
        let store = SessionStore(defaults: defaults, service: "ru.itmo.talkmate.tests")
        store.clear()
        XCTAssertFalse(store.isLoggedIn)
        store.save(AuthResult(token: "tok", user: User(id: 1, name: "Эдна", email: "e@itmo.ru")))
        XCTAssertTrue(store.isLoggedIn)
        XCTAssertEqual(store.token, "tok")
        XCTAssertEqual(store.userName, "Эдна")
        // Токен лежит в связке ключей, а не в настройках приложения.
        XCTAssertFalse(defaults.dictionaryRepresentation().values.contains { ($0 as? String) == "tok" })
        store.serverURL = " http://192.168.1.10:5050 "
        XCTAssertEqual(store.serverURL, "http://192.168.1.10:5050")
        store.clear()
        XCTAssertNil(store.token)
        XCTAssertEqual(store.userName, "")
        XCTAssertEqual(store.serverURL, "http://192.168.1.10:5050")
    }
}

final class ArtTests: XCTestCase {
    func testSvgPathsAreParsedAndScaled() {
        let rect = CGRect(x: 0, y: 0, width: 128, height: 168)
        let all = [Art.star, Art.asterisk, Art.flower, Art.backArrow, Art.decor, Art.micBody, Art.micGrille, Art.micHolder,
                   Art.micBase, Art.micAccents, Art.squiggleAccents, Art.book, Art.bars, Art.chevron, Art.squiggle]
        for data in all {
            let path = SVGShape(data: data, viewBox: CGSize(width: 64, height: 84)).path(in: rect)
            XCTAssertFalse(path.isEmpty, data)
            XCTAssertGreaterThan(max(path.boundingRect.width, path.boundingRect.height), 4, data)
        }
        // Стойка микрофона: отрезок от (84,120) до (84,154) в поле 64x84, растянутом вдвое.
        let stand = SVGShape(data: Art.micStand, viewBox: CGSize(width: 64, height: 84)).path(in: rect).boundingRect
        XCTAssertEqual(stand.minX, 168, accuracy: 0.01)
        XCTAssertEqual(stand.minY, 240, accuracy: 0.01)
        XCTAssertEqual(stand.maxY, 308, accuracy: 0.01)
        // Решётка микрофона: шесть отдельных штрихов, команда M встречается в середине строки.
        let grille = SVGShape(data: Art.micGrille, viewBox: CGSize(width: 64, height: 84)).path(in: rect).boundingRect
        XCTAssertEqual(grille.minX, 136, accuracy: 0.01)
        XCTAssertEqual(grille.maxX, 208, accuracy: 0.01)
    }

    func testSlidesReportIsDecodedAndFormatted() throws {
        let json = """
        {"id":1,"feedback":{"speech_rate":110,"volume":"normal","monotony":"expressive","num_fillers":0},
         "slides":{"pages":2,"coverage":55,"reading":10,"notes":["Слайд 2: мелко"],
          "items":[{"page":1,"title":"Цель","seconds":42,"coverage":80,"reading":0,"missed":[],"status":"covered","dense":false,"small_text":false},
                   {"page":2,"title":"Схема","seconds":0,"coverage":null,"reading":0,"missed":["сервер"],"status":"no_text","dense":true,"small_text":true}]}}
        """
        let report = try XCTUnwrap(JSONDecoder().decode(SpeechResult.self, from: Data(json.utf8)).slides)
        XCTAssertEqual(report.pages, 2)
        XCTAssertEqual(report.items?[1].coverage, nil)
        XCTAssertEqual(report.items?[1].smallText, true)
        XCTAssertEqual(Formatters.slideLine(try XCTUnwrap(report.items?.first)), "0:42 · раскрыт на 80%")
        XCTAssertEqual(Formatters.slideLine(try XCTUnwrap(report.items?.last)), "0:00 · без текста · много текста · мелкий шрифт")
    }

    func testEnglishInterfaceUsesEnglishWords() {
        Lang.forced = "en"
        defer { Lang.forced = "ru" }
        XCTAssertEqual(Formatters.rate(115), "115 wpm")
        XCTAssertEqual(Formatters.volume("quiet"), "quiet")
        XCTAssertEqual(Formatters.fillers(1), "1 word")
        XCTAssertEqual(Formatters.fillers(5), "5 words")
        XCTAssertEqual(Formatters.monotonyDescription("monotone"), "monotone")
        XCTAssertEqual(Validation.email("oops"), "Enter a valid email")
        XCTAssertEqual(Lang.code, "en")
    }
}
