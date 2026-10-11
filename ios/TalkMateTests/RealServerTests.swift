import XCTest
@testable import TalkMate

/// Сквозная проверка клиента на живом сервере. Обычный прогон её пропускает. Запуск при работающем backend/run.sh:
/// TEST_RUNNER_TALKMATE_SERVER=http://localhost:5050 xcodebuild ... -only-testing:TalkMateTests/RealServerTests test
final class RealServerTests: XCTestCase {
    func testFullCycleAgainstRealServer() async throws {
        guard let server = ProcessInfo.processInfo.environment["TALKMATE_SERVER"] else {
            throw XCTSkip("TALKMATE_SERVER не задан")
        }
        var token: String?
        let api = HttpApi(baseURL: { server }, token: { token })

        let email = "ios_\(Int(Date().timeIntervalSince1970))@talkmate.test"
        let registered = try await api.register(RegisterRequest(name: "Эдна", email: email, password: "password", birthDate: "2001-05-17", gender: "female"))
        token = registered.token
        let again = try await api.login(email: email, password: "password")
        XCTAssertEqual(again.user.email, email)
        do {
            _ = try await api.login(email: email, password: "wrong-password")
            XCTFail("вход с неверным паролем должен быть отклонён")
        } catch let error as ApiError {
            XCTAssertEqual(error.kind, .rejected)
        }

        let articles = try await api.articles()
        XCTAssertGreaterThanOrEqual(articles.count, 4)
        XCTAssertEqual(articles.first?.title, "Жестикуляция и движение")
        let first = try await api.article(id: articles[0].id)
        XCTAssertTrue(first.content.contains("Михаила Чехова"))

        let audio = try XCTUnwrap(Bundle(for: Self.self).url(forResource: "demo_speech", withExtension: "wav"))
        let result = try await api.uploadSpeech(file: audio)
        XCTAssertTrue(result.text.lowercased().contains("коллеги"), result.text)
        XCTAssertTrue((60...220).contains(result.feedback.speechRate), "\(result.feedback.speechRate)")
        XCTAssertGreaterThanOrEqual(result.feedback.numFillers, 2)
        XCTAssertFalse(result.recommendation?.description.isEmpty ?? true)

        let stats = try await api.stats()
        XCTAssertEqual(stats.points.count, 1)
        XCTAssertEqual(stats.points[0].speechRate, result.feedback.speechRate)
        XCTAssertEqual(stats.thresholds["rate_slow"], 90)

        // Запрос кода восстановления отвечает одинаково для любого адреса.
        try await api.requestPasswordReset(email: email)
        try await api.requestPasswordReset(email: "ghost@talkmate.test")
        do {
            _ = try await api.resetPassword(email: email, code: "000000", newPassword: "newpass1")
            XCTFail("неверный код должен быть отклонён")
        } catch let error as ApiError {
            XCTAssertEqual(error.code, "invalid_code")
        }

        token = "broken"
        do {
            _ = try await api.stats()
            XCTFail("запрос с испорченным токеном должен быть отклонён")
        } catch let error as ApiError {
            XCTAssertEqual(error.kind, .unauthorized)
        }
    }
}
