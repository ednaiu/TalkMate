import Foundation
import Security

/// Хранит токен в связке ключей, имя и адрес сервера в настройках приложения.
final class SessionStore {
    private let defaults: UserDefaults
    private let service: String

    init(defaults: UserDefaults = .standard, service: String = "ru.itmo.talkmate.session") {
        self.defaults = defaults
        self.service = service
    }

    var token: String? { keychainRead() }
    var isLoggedIn: Bool { !(token ?? "").isEmpty }
    var userName: String { defaults.string(forKey: "userName") ?? "" }
    var userEmail: String { defaults.string(forKey: "userEmail") ?? "" }

    var serverURL: String {
        get {
            if let saved = defaults.string(forKey: "serverURL"), !saved.trimmingCharacters(in: .whitespaces).isEmpty { return saved }
            return Bundle.main.object(forInfoDictionaryKey: "TalkMateServerURL") as? String ?? "http://localhost:5050"
        }
        set { defaults.set(newValue.trimmingCharacters(in: .whitespaces), forKey: "serverURL") }
    }

    func save(_ result: AuthResult) {
        keychainWrite(result.token)
        defaults.set(result.user.name, forKey: "userName")
        defaults.set(result.user.email, forKey: "userEmail")
    }

    func clear() {
        keychainDelete()
        defaults.removeObject(forKey: "userName")
        defaults.removeObject(forKey: "userEmail")
    }

    // MARK: - Keychain

    private var query: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: "token"]
    }

    private func keychainRead() -> String? {
        var request = query
        request[kSecReturnData as String] = true
        request[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?
        guard SecItemCopyMatching(request as CFDictionary, &item) == errSecSuccess, let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    private func keychainWrite(_ value: String) {
        keychainDelete()
        var request = query
        request[kSecValueData as String] = Data(value.utf8)
        request[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        SecItemAdd(request as CFDictionary, nil)
    }

    private func keychainDelete() {
        SecItemDelete(query as CFDictionary)
    }
}
