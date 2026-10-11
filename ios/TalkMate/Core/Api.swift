import Foundation

struct ApiError: Error, Equatable {
    enum Kind { case network, unauthorized, rejected, server }

    let kind: Kind
    let message: String
    var code: String = ""

    /// Превращает ответ с ошибкой в текст, который можно показать пользователю.
    static func from(status: Int, body: Data) -> ApiError {
        let json = (try? JSONSerialization.jsonObject(with: body)) as? [String: Any]
        let code = json?["error"] as? String ?? ""
        let message = json?["message"] as? String ?? ""
        if status == 401 && code != "invalid_credentials" {
            return ApiError(kind: .unauthorized, message: message.isEmpty ? L("Войдите снова", "Please log in again") : message, code: code)
        }
        if (400...499).contains(status) {
            return ApiError(kind: .rejected, message: message.isEmpty ? L("Запрос отклонён (\(status))", "Request rejected (\(status))") : message, code: code)
        }
        return ApiError(kind: .server, message: message.isEmpty ? L("Сервер недоступен (\(status))", "Server unavailable (\(status))") : message, code: code)
    }

    static var network: ApiError { ApiError(kind: .network, message: L("Нет связи с сервером. Проверьте подключение к сети", "No connection to the server. Check your network")) }
    static var badResponse: ApiError { ApiError(kind: .server, message: L("Сервер вернул непонятный ответ", "The server returned an unreadable response")) }
}

protocol Api {
    func register(_ request: RegisterRequest) async throws -> AuthResult
    func login(email: String, password: String) async throws -> AuthResult
    /// Просит сервер выслать код восстановления. Ответ одинаков для любого адреса.
    func requestPasswordReset(email: String) async throws
    /// Меняет пароль по коду из письма и сразу входит в систему.
    func resetPassword(email: String, code: String, newPassword: String) async throws -> AuthResult
    func articles() async throws -> [ArticleSummary]
    func article(id: Int) async throws -> Article
    /// Отправляет запись на разбор. Презентацию в PDF можно приложить, тогда сервер сравнит её с речью.
    func uploadSpeech(file: URL, slides: URL?, marks: [SlideMark]) async throws -> SpeechResult
    func stats() async throws -> Stats
    func profile() async throws -> Profile
    /// Все тренировки коротко, новые сверху.
    func trainings() async throws -> [TrainingBrief]
    /// Разбор одной тренировки целиком: по нему открывается экран результатов.
    func speech(id: Int) async throws -> SpeechResult
}

extension Api {
    func uploadSpeech(file: URL) async throws -> SpeechResult { try await uploadSpeech(file: file, slides: nil, marks: []) }
}

final class HttpApi: Api {
    private let baseURL: () -> String
    private let token: () -> String?
    private let session: URLSession

    init(baseURL: @escaping () -> String, token: @escaping () -> String?, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.token = token
        self.session = session
    }

    func register(_ request: RegisterRequest) async throws -> AuthResult {
        try await send("POST", "/api/auth/register", json: request.json)
    }

    func login(email: String, password: String) async throws -> AuthResult {
        try await send("POST", "/api/auth/login", json: ["email": email, "password": password])
    }

    func requestPasswordReset(email: String) async throws {
        _ = try await data("POST", "/api/auth/forgot", json: ["email": email])
    }

    func resetPassword(email: String, code: String, newPassword: String) async throws -> AuthResult {
        try await send("POST", "/api/auth/reset", json: ["email": email, "code": code, "password": newPassword])
    }

    func articles() async throws -> [ArticleSummary] { try await send("GET", "/api/articles") }

    func article(id: Int) async throws -> Article { try await send("GET", "/api/articles/\(id)") }

    func stats() async throws -> Stats { try await send("GET", "/api/stats") }

    func profile() async throws -> Profile { try await send("GET", "/api/profile") }

    func trainings() async throws -> [TrainingBrief] { try await send("GET", "/api/trainings") }

    func speech(id: Int) async throws -> SpeechResult { try await send("GET", "/api/speeches/\(id)") }

    func uploadSpeech(file: URL, slides: URL?, marks: [SlideMark]) async throws -> SpeechResult {
        let boundary = "talkmate" + UUID().uuidString.replacingOccurrences(of: "-", with: "")
        var body = Data()
        func part(_ name: String, _ filename: String, _ type: String, _ url: URL) throws {
            body.append("--\(boundary)\r\nContent-Disposition: form-data; name=\"\(name)\"; filename=\"\(filename)\"\r\nContent-Type: \(type)\r\n\r\n".data(using: .utf8)!)
            body.append(try Data(contentsOf: url))
            body.append("\r\n".data(using: .utf8)!)
        }
        try part("audio", "speech.wav", "audio/wav", file)
        if let slides {
            try part("slides", "slides.pdf", "application/pdf", slides)
            // Отметки о смене слайдов идут текстовым полем рядом с файлами.
            if !marks.isEmpty, let json = try? JSONSerialization.data(withJSONObject: marks.map { ["page": $0.page, "start": $0.start] }) {
                body.append("--\(boundary)\r\nContent-Disposition: form-data; name=\"slide_times\"\r\n\r\n".data(using: .utf8)!)
                body.append(json)
                body.append("\r\n".data(using: .utf8)!)
            }
        }
        body.append("--\(boundary)--\r\n".data(using: .utf8)!)
        var request = try makeRequest("POST", "/api/speeches")
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.httpBody = body
        // Разбор длинной записи с моделью эмоций занимает до нескольких минут.
        request.timeoutInterval = 300
        return try decode(try await perform(request))
    }

    // MARK: -

    private func send<T: Decodable>(_ method: String, _ path: String, json: [String: Any]? = nil) async throws -> T {
        try decode(try await data(method, path, json: json))
    }

    private func data(_ method: String, _ path: String, json: [String: Any]? = nil) async throws -> Data {
        var request = try makeRequest(method, path)
        if let json {
            request.setValue("application/json; charset=utf-8", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONSerialization.data(withJSONObject: json)
        }
        return try await perform(request)
    }

    private func makeRequest(_ method: String, _ path: String) throws -> URLRequest {
        let base = baseURL().trimmingCharacters(in: CharacterSet(charactersIn: "/ "))
        guard let url = URL(string: base + path) else {
            throw ApiError(kind: .network, message: L("Неверный адрес сервера", "Wrong server address"))
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = 20
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        // Язык интерфейса: на нём сервер пишет рекомендации и сообщения об ошибках.
        request.setValue(Lang.code, forHTTPHeaderField: "Accept-Language")
        if let token = token() { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        return request
    }

    private func perform(_ request: URLRequest) async throws -> Data {
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw ApiError.network
        }
        guard let http = response as? HTTPURLResponse else { throw ApiError.badResponse }
        guard (200...299).contains(http.statusCode) else { throw ApiError.from(status: http.statusCode, body: data) }
        return data
    }

    private func decode<T: Decodable>(_ data: Data) throws -> T {
        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            throw ApiError.badResponse
        }
    }
}
