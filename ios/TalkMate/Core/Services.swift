import Foundation
import SwiftUI

/// Точка сборки зависимостей. В UI-тестах сервер и диктофон подменяются (см. Fakes.swift).
final class Services {
    let session: SessionStore
    let api: Api
    let makeRecorder: () -> Recorder
    let requestMicrophone: () async -> Bool

    init(session: SessionStore, api: Api, makeRecorder: @escaping () -> Recorder, requestMicrophone: @escaping () async -> Bool) {
        self.session = session
        self.api = api
        self.makeRecorder = makeRecorder
        self.requestMicrophone = requestMicrophone
    }

    static func live() -> Services {
        let session = SessionStore()
        return Services(
            session: session,
            api: HttpApi(baseURL: { session.serverURL }, token: { session.token }),
            makeRecorder: { WavRecorder() },
            requestMicrophone: { await WavRecorder.requestPermission() }
        )
    }
}

enum Route: Hashable {
    case login
    case signUp
    case resetPassword(email: String)
    case record
    case results(SpeechResult)
    case articles
    case article(ArticleSummary)
    case stats
    case profile
    case trainings
}

@MainActor
final class AppState: ObservableObject {
    let services: Services
    @Published var path: [Route] = []
    @Published private(set) var isLoggedIn: Bool
    @Published private(set) var userName: String
    @Published var notice: String?
    /// Меняется при смене языка: по нему корневой экран перерисовывается целиком.
    @Published private(set) var languageTick = 0

    func setLanguage(_ code: String?) {
        Lang.chosen = code
        languageTick += 1
    }

    init(services: Services) {
        self.services = services
        isLoggedIn = services.session.isLoggedIn
        userName = services.session.userName
    }

    var userEmail: String { services.session.userEmail }

    func signedIn(_ result: AuthResult) {
        services.session.save(result)
        userName = result.user.name
        path = []
        isLoggedIn = true
    }

    func logout(notice: String? = nil) {
        services.session.clear()
        path = []
        isLoggedIn = false
        self.notice = notice
    }

    func back() {
        if !path.isEmpty { path.removeLast() }
    }

    /// Выполняет запрос. Истёкшая сессия всегда ведёт на первый экран, остальные ошибки возвращаются вызывающему.
    func call<T>(_ request: @escaping (Api) async throws -> T) async -> Result<T, ApiError> {
        do {
            return .success(try await request(services.api))
        } catch let error as ApiError {
            if error.kind == .unauthorized {
                logout(notice: L("Сессия истекла, войдите снова", "Your session has expired, please log in again"))
            }
            return .failure(error)
        } catch {
            return .failure(ApiError(kind: .server, message: L("Что-то пошло не так", "Something went wrong")))
        }
    }
}
