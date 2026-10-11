import SwiftUI

@main
struct TalkMateApp: App {
    @StateObject private var app: AppState

    init() {
        #if DEBUG
        if ProcessInfo.processInfo.arguments.contains("-uiTesting") {
            _app = StateObject(wrappedValue: AppState(services: .uiTesting(environment: ProcessInfo.processInfo.environment)))
            UIView.setAnimationsEnabled(false)
            TMField.autofill = false
            TMField.maskPasswords = false
            return
        }
        #endif
        _app = StateObject(wrappedValue: AppState(services: .live()))
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .id(app.languageTick)
                .environmentObject(app)
                .preferredColorScheme(.light)
        }
    }
}

struct RootView: View {
    @EnvironmentObject private var app: AppState

    var body: some View {
        NavigationStack(path: $app.path) {
            Group {
                if app.isLoggedIn { HomeView() } else { WelcomeView() }
            }
            .toolbar(.hidden, for: .navigationBar)
            .navigationDestination(for: Route.self) { route in
                destination(route).toolbar(.hidden, for: .navigationBar)
            }
        }
    }

    @ViewBuilder
    private func destination(_ route: Route) -> some View {
        switch route {
        case .login: LoginView()
        case .signUp: SignUpView()
        case .resetPassword(let email): ResetPasswordView(email: email)
        case .record: RecordView()
        case .results(let result): ResultsView(result: result)
        case .articles: ArticlesView()
        case .article(let summary): ArticleView(summary: summary)
        case .stats: StatsView()
        case .profile: ProfileView()
        case .trainings: TrainingsView()
        }
    }
}
