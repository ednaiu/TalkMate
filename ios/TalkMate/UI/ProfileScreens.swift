import SwiftUI

/// Нижняя панель трёх главных разделов. Переключение заменяет стек экранов целиком.
struct BottomBar: View {
    enum Tab { case home, trainings, profile }

    @EnvironmentObject private var app: AppState
    let selected: Tab

    var body: some View {
        HStack(spacing: 0) {
            item(.home, icon: "house", title: L("Главная", "Home"), id: "navHome") { app.path = [] }
            item(.trainings, icon: "chart.bar.fill", title: L("Тренировки", "Sessions"), id: "navTrainings") { app.path = [.trainings] }
            item(.profile, icon: "person.fill", title: L("Профиль", "Profile"), id: "navProfile") { app.path = [.profile] }
        }
        .padding(.top, 8)
        .background(Color.white.shadow(color: .black.opacity(0.08), radius: 6, y: -2).ignoresSafeArea(edges: .bottom))
    }

    private func item(_ tab: Tab, icon: String, title: String, id: String, action: @escaping () -> Void) -> some View {
        Button { if tab != selected { action() } } label: {
            VStack(spacing: 3) {
                Image(systemName: icon).font(.interface(21))
                Text(title).font(.interface(12))
            }
            .foregroundStyle(tab == selected ? Color.tmBlueStrong : Color.tmGreyText)
            .frame(maxWidth: .infinity, minHeight: 48)
            .contentShape(Rectangle())
        }
        .accessibilityIdentifier(id)
        .accessibilityAddTraits(tab == selected ? .isSelected : [])
    }
}

/// Строка тренировки в списке. Нажатие загружает разбор и открывает экран результатов.
struct TrainingRow: View {
    @EnvironmentObject private var app: AppState
    let item: TrainingBrief
    @Binding var error: ApiError?

    var body: some View {
        Button {
            Task {
                switch await app.call({ try await $0.speech(id: item.id) }) {
                case .success(let result): app.path.append(.results(result))
                case .failure(let failure): error = failure
                }
            }
        } label: {
            HStack(spacing: 14) {
                Image(systemName: "mic.fill").font(.interface(18)).foregroundStyle(Color.tmBlueStrong)
                    .frame(width: 44, height: 44).background(Circle().fill(Color(hex: 0xEEF0FB)))
                VStack(alignment: .leading, spacing: 2) {
                    Text(item.title).font(.interface(16)).foregroundStyle(Color.tmInk).lineLimit(1)
                    Text(Formatters.trainingMeta(item)).font(.interface(14)).foregroundStyle(Color.tmGreyText)
                }
                Spacer(minLength: 4)
                Image(systemName: "chevron.right").font(.interface(14, weight: .semibold)).foregroundStyle(Color.tmBlueBright)
            }
            .padding(14)
            .background(RoundedRectangle(cornerRadius: 22).fill(.white))
        }
        .accessibilityIdentifier("training\(item.id)")
    }
}

/// Маленький график темпа: точки последних тренировок на фоне полосы нормы.
struct TempoChart: View {
    let points: [TempoPoint]
    let slow: Double
    let fast: Double

    var body: some View {
        Canvas { context, size in
            guard !points.isEmpty else { return }
            let values = points.map { Double($0.rate) }
            let side: CGFloat = 18, top: CGFloat = 6, bottom = size.height - 22
            let low = min(values.min() ?? slow, slow) - 8, high = max(values.max() ?? fast, fast) + 8
            func y(_ value: Double) -> CGFloat { bottom - CGFloat((value - low) / (high - low)) * (bottom - top) }
            func x(_ index: Int) -> CGFloat { points.count == 1 ? size.width / 2 : side + CGFloat(index) * (size.width - 2 * side) / CGFloat(points.count - 1) }

            context.fill(Path(CGRect(x: side, y: y(fast), width: size.width - 2 * side, height: y(slow) - y(fast))), with: .color(.tmPink))
            var line = Path()
            for (index, value) in values.enumerated() {
                var grid = Path()
                grid.move(to: CGPoint(x: x(index), y: top))
                grid.addLine(to: CGPoint(x: x(index), y: bottom))
                context.stroke(grid, with: .color(Color(hex: 0xDDDEE6)), style: StrokeStyle(lineWidth: 1, dash: [4, 4]))
                context.draw(Text(Formatters.dayMonth(points[index].date, short: true)).font(.interface(12)).foregroundColor(.tmGreyText),
                             at: CGPoint(x: x(index), y: size.height - 8))
                let point = CGPoint(x: x(index), y: y(value))
                if index == 0 { line.move(to: point) } else { line.addLine(to: point) }
            }
            context.stroke(line, with: .color(.tmBlue), style: StrokeStyle(lineWidth: 2.5, lineCap: .round, lineJoin: .round))
            for (index, value) in values.enumerated() {
                context.fill(Path(ellipseIn: CGRect(x: x(index) - 4.5, y: y(value) - 4.5, width: 9, height: 9)), with: .color(.tmBlue))
            }
        }
        .accessibilityLabel(points.map { String($0.rate) }.joined(separator: ", "))
    }
}

/// Личный кабинет: счётчики тренировок, темп последних записей и список недавних тренировок.
struct ProfileView: View {
    @EnvironmentObject private var app: AppState
    @State private var profile: Profile?
    @State private var error: ApiError?
    @State private var plansShown = false

    private var name: String { profile?.user?.name ?? app.userName }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                header
                Text(L("Твой прогресс", "Your progress")).font(.interface(23, weight: .semibold)).foregroundStyle(Color.tmInk)
                    .padding(.horizontal, 20).padding(.top, 18)
                counters.padding(.horizontal, 14).padding(.top, 10)
                tempo.padding(.horizontal, 14).padding(.top, 10)
                Button(L("Начать тренировку", "Start practice")) { app.path.append(.record) }
                    .buttonStyle(StrongButtonStyle()).padding(.horizontal, 14).padding(.top, 12)
                    .accessibilityIdentifier("btnStartTraining")
                HStack {
                    Text(L("Последние тренировки", "Recent sessions")).font(.interface(20, weight: .semibold)).foregroundStyle(Color.tmInk)
                    Spacer()
                    Button(L("Все", "All")) { app.path = [.trainings] }
                        .font(.interface(17, weight: .semibold)).foregroundStyle(Color.tmBlueStrong).frame(minHeight: 44)
                        .accessibilityIdentifier("tvAll")
                }
                .padding(.horizontal, 20).padding(.top, 10)
                VStack(spacing: 8) {
                    ForEach(profile?.recent ?? []) { TrainingRow(item: $0, error: $error) }
                    if let profile, profile.recent.isEmpty {
                        Text(L("Тренировок пока нет", "No sessions yet")).font(.interface(15)).foregroundStyle(Color.tmGreyText)
                            .frame(maxWidth: .infinity, alignment: .leading).padding(.leading, 6)
                    }
                }
                .padding(.horizontal, 14)
                plans.padding(.horizontal, 14).padding(.top, 12)
            }
            .padding(.bottom, 20)
        }
        // Розовая шапка продолжается под строку состояния.
        .background(ZStack(alignment: .top) { Color.tmPaper; Color.tmPink.frame(height: 140) }.ignoresSafeArea())
        .safeAreaInset(edge: .bottom, spacing: 0) { BottomBar(selected: .profile) }
        .task { await load() }
        .errorScreen($error, onBack: {}, onRetry: { Task { await load() } })
        .alert(L("Сейчас есть только базовый план: все функции приложения открыты бесплатно.",
                 "Only the basic plan exists for now: every feature of the app is free."), isPresented: $plansShown) {
            Button(L("Закрыть", "Close"), role: .cancel) {}
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text("Talk Mate").font(.wordmark(19)).foregroundStyle(Color.tmFieldLabel)
                Spacer()
                Button { app.path.append(.settings) } label: {
                    Image(systemName: "gearshape").font(.interface(22)).foregroundStyle(Color.tmFieldLabel).frame(width: 44, height: 44)
                }
                .accessibilityLabel(L("Настройки", "Settings")).accessibilityIdentifier("btnSettings")
            }
            HStack(spacing: 14) {
                Text(String(name.trimmingCharacters(in: .whitespaces).prefix(1)).uppercased())
                    .font(.interface(24)).foregroundStyle(Color.tmFieldLabel)
                    .frame(width: 60, height: 60).background(Circle().fill(.white))
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 6) {
                    Text(name).font(.interface(21, weight: .semibold)).foregroundStyle(Color.tmInk).lineLimit(2)
                        .accessibilityIdentifier("tvName")
                    Text(L("Базовый план", "Basic plan")).font(.interface(13)).foregroundStyle(Color.tmGreyTitle)
                        .padding(.horizontal, 12).padding(.vertical, 4)
                        .overlay(Capsule().stroke(Color(hex: 0xB9BBC8), lineWidth: 1))
                }
                Spacer(minLength: 0)
                WelcomeArt(blob: .tmPinkShape).frame(width: 130)
            }
        }
        .padding(.leading, 20).padding(.trailing, 12).padding(.top, 8).padding(.bottom, 14)
        .background(UnevenRoundedRectangle(bottomLeadingRadius: 34, bottomTrailingRadius: 34).fill(Color.tmPink).ignoresSafeArea(edges: .top))
    }

    private var counters: some View {
        HStack(spacing: 0) {
            counter("chart.bar.fill", profile?.count ?? 0, Formatters.trainingsWord(profile?.count ?? 0), id: "tvCount")
            Divider().frame(height: 44)
            counter("clock", profile?.minutes ?? 0, Formatters.minutesWord(profile?.minutes ?? 0), id: "tvMinutes")
            Divider().frame(height: 44)
            counter("flame", profile?.streak ?? 0, Formatters.streakWord(profile?.streak ?? 0), id: "tvStreak")
        }
        .padding(.vertical, 16)
        .background(RoundedRectangle(cornerRadius: 22).fill(.white))
    }

    private func counter(_ icon: String, _ value: Int, _ caption: String, id: String) -> some View {
        VStack(spacing: 2) {
            HStack(spacing: 8) {
                Image(systemName: icon).font(.interface(20)).foregroundStyle(Color.tmBlueStrong)
                Text("\(value)").font(.interface(26, weight: .semibold)).foregroundStyle(Color.tmInk).accessibilityIdentifier(id)
            }
            Text(caption).font(.interface(13)).foregroundStyle(Color.tmGreyText).multilineTextAlignment(.center)
                .accessibilityIdentifier(id + "Caption")
        }
        .frame(maxWidth: .infinity)
    }

    private var tempo: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(L("Темп речи", "Speech pace")).font(.interface(20, weight: .semibold)).foregroundStyle(Color.tmInk)
            if let points = profile?.tempo, let last = points.last {
                Text(Formatters.lastTrainings(points.count)).font(.interface(15)).foregroundStyle(Color.tmGreyText)
                    .accessibilityIdentifier("tvTempoPeriod")
                HStack(spacing: 10) {
                    VStack(alignment: .leading, spacing: 0) {
                        Text("\(last.rate)").font(.interface(38, weight: .bold)).foregroundStyle(Color.tmInk).accessibilityIdentifier("tvTempoValue")
                        Text(Formatters.wordsPerMinute(last.rate)).font(.interface(14)).foregroundStyle(Color.tmGreyText)
                    }
                    TempoChart(points: points, slow: profile?.rateSlow ?? 90, fast: profile?.rateFast ?? 140).frame(height: 110)
                }
                .padding(.top, 8)
            } else {
                Text(L("График появится после первой тренировки", "The chart appears after your first session"))
                    .font(.interface(15)).foregroundStyle(Color.tmGreyText)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(18)
        .background(RoundedRectangle(cornerRadius: 22).fill(.white))
    }

    private var plans: some View {
        Button { plansShown = true } label: {
            HStack(spacing: 8) {
                WelcomeArt(blob: .tmPinkShape).frame(width: 70)
                Text(L("Больше возможностей\nдля практики", "More ways\nto practice")).font(.interface(16, weight: .semibold))
                    .foregroundStyle(Color.tmInk).multilineTextAlignment(.leading)
                Spacer(minLength: 4)
                Text(L("Посмотреть тарифы ›", "See plans ›")).font(.interface(14, weight: .semibold)).foregroundStyle(Color.tmBlueStrong)
            }
            .padding(12)
            .background(RoundedRectangle(cornerRadius: 22).fill(Color.tmPinkCard))
        }
        .accessibilityIdentifier("cardPlans")
    }

    private func load() async {
        switch await app.call({ try await $0.profile() }) {
        case .success(let loaded): profile = loaded
        case .failure(let failure): error = failure
        }
    }
}

/// Все тренировки пользователя.
struct TrainingsView: View {
    @EnvironmentObject private var app: AppState
    @State private var items: [TrainingBrief]?
    @State private var error: ApiError?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 8) {
                Text(L("Тренировки", "Sessions")).font(.interface(26, weight: .semibold)).foregroundStyle(Color.tmInk)
                    .padding(.leading, 6).padding(.top, 16).padding(.bottom, 4).accessibilityIdentifier("tvTitle")
                if let items {
                    ForEach(items) { TrainingRow(item: $0, error: $error) }
                    if items.isEmpty {
                        Text(L("Тренировок пока нет", "No sessions yet")).font(.interface(16)).foregroundStyle(Color.tmGreyText).padding(.leading, 6)
                    }
                } else {
                    ProgressView().tint(.tmBlueStrong).frame(maxWidth: .infinity).padding(.top, 24)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 14).padding(.bottom, 20)
        }
        .background(Color.tmPaper.ignoresSafeArea())
        .safeAreaInset(edge: .bottom, spacing: 0) { BottomBar(selected: .trainings) }
        .task { await load() }
        .errorScreen($error, onBack: {}, onRetry: { Task { await load() } })
    }

    private func load() async {
        switch await app.call({ try await $0.trainings() }) {
        case .success(let loaded): items = loaded
        case .failure(let failure): error = failure
        }
    }
}

/// Настройки доступны из профиля и сохраняются между запусками приложения.
struct SettingsView: View {
    @EnvironmentObject private var app: AppState
    @AppStorage("settingsServerDraft") private var address = ""
    @State private var addressError: String?
    @State private var saved = false
    @State private var logoutShown = false

    @State private var checking = false
    @State private var connectionMessage: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                HStack(alignment: .center, spacing: 16) {
                    BackButton()
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Talk Mate").font(.wordmark(19)).foregroundStyle(Color.tmFieldLabel)
                        Text(L("Настройки", "Settings")).font(.interface(28, weight: .semibold))
                            .accessibilityIdentifier("settingsTitle")
                    }
                    Spacer(minLength: 0)
                    WelcomeArt(blob: .tmPinkShape).frame(width: 90).accessibilityHidden(true)
                }
                .padding(.horizontal, 20).padding(.vertical, 16)
                .background(UnevenRoundedRectangle(bottomLeadingRadius: 34, bottomTrailingRadius: 34)
                    .fill(Color.tmPink).ignoresSafeArea(edges: .top))

                VStack(alignment: .leading, spacing: 18) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(L("Язык приложения", "App language")).font(.interface(20, weight: .semibold))
                        Text(L("Выбери удобный язык интерфейса", "Choose your interface language"))
                            .font(.interface(15)).foregroundStyle(Color.tmGreyText).padding(.bottom, 10)
                        languageOption(L("Как в системе", "System default"), code: nil, id: "languageSystem")
                        Divider()
                        languageOption("Русский", code: "ru", id: "languageRussian")
                        Divider()
                        languageOption("English", code: "en", id: "languageEnglish")
                    }
                    .padding(20).background(RoundedRectangle(cornerRadius: 22).fill(.white))

                    VStack(alignment: .leading, spacing: 14) {
                        Text(L("Подключение", "Connection")).font(.interface(20, weight: .semibold))
                        Text(L("Телефон и компьютер с сервером должны быть в одной сети Wi-Fi.",
                               "Your phone and the server computer must be on the same Wi-Fi network."))
                            .font(.interface(15)).foregroundStyle(Color.tmGreyText)
                        AuthField(label: L("Адрес сервера", "Server address"), hint: "http://192.168.1.42:5050",
                                  text: $address, id: "serverAddress", keyboard: .URL)
                            .onChange(of: address) { _, _ in addressError = nil; saved = false; connectionMessage = nil }
                        if let addressError {
                            Text(addressError).font(.interface(14)).foregroundStyle(.red)
                                .accessibilityIdentifier("serverAddressError")
                        }
                        if saved {
                            Label(L("Адрес сохранён", "Address saved"), systemImage: "checkmark.circle.fill")
                                .font(.interface(15)).foregroundStyle(Color.tmBlueStrong)
                                .accessibilityIdentifier("serverAddressSaved")
                        }
                        Button(L("Сохранить адрес", "Save address")) { saveAddress() }
                            .buttonStyle(StrongButtonStyle()).accessibilityIdentifier("saveServerAddress")
                        Button(checking ? L("Проверяем…", "Checking…") : L("Проверить соединение", "Check connection")) {
                            Task { await checkConnection() }
                        }
                        .buttonStyle(OutlineButtonStyle()).disabled(checking)
                        .accessibilityIdentifier("checkServerConnection")
                        if let connectionMessage {
                            Text(connectionMessage).font(.interface(15)).foregroundStyle(Color.tmGreyText)
                                .accessibilityIdentifier("serverConnectionStatus")
                        }
                    }
                    .padding(20).background(RoundedRectangle(cornerRadius: 22).fill(.white))

                    Button(role: .destructive) { logoutShown = true } label: {
                        Text(L("Выйти из аккаунта", "Log out")).frame(maxWidth: .infinity, minHeight: 48)
                    }
                    .accessibilityIdentifier("btnLogout")
                }
                .padding(14)
            }
        }
        .foregroundStyle(Color.tmInk)
        .background(ZStack(alignment: .top) { Color.tmPaper; Color.tmPink.frame(height: 140) }.ignoresSafeArea())
        .scrollDismissesKeyboard(.interactively)
        .toolbar {
            ToolbarItemGroup(placement: .keyboard) {
                Spacer()
                Button(L("Готово", "Done")) { hideKeyboard() }.accessibilityIdentifier("btnKeyboardDone")
            }
        }
        .onAppear { if address.isEmpty { address = app.services.session.serverURL } }
        .confirmationDialog(L("Выйти из аккаунта?", "Log out of your account?"), isPresented: $logoutShown, titleVisibility: .visible) {
            Button(L("Выйти", "Log out"), role: .destructive) { app.logout() }
            Button(L("Отмена", "Cancel"), role: .cancel) {}
        }
    }

    @MainActor
    private func checkConnection() async {
        addressError = Validation.serverURL(address)
        guard addressError == nil else { return }
        let checkedAddress = address.trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        guard let url = URL(string: checkedAddress + "/api/health") else { return }
        checking = true
        connectionMessage = nil
        defer { checking = false }
        do {
            let (data, response) = try await URLSession.shared.data(for: URLRequest(url: url, timeoutInterval: 8))
            let json = try? JSONSerialization.jsonObject(with: data) as? [String: String]
            guard (response as? HTTPURLResponse)?.statusCode == 200, json?["status"] == "ok" else {
                connectionMessage = L("По этому адресу сервер TalkMate не отвечает.", "No TalkMate server responds at this address.")
                return
            }
            connectionMessage = L("Соединение установлено. Сервер доступен.", "Connected. The server is available.")
        } catch {
            connectionMessage = L("Нет связи. Проверь адрес, Wi-Fi и разрешение «Локальная сеть» в настройках iPhone для TalkMate.",
                                  "No connection. Check the address, Wi-Fi and Local Network permission for TalkMate in iPhone Settings.")
        }
    }

    private func languageOption(_ title: String, code: String?, id: String) -> some View {
        Button {
            // Сохраняем введённый адрес при пересоздании интерфейса после смены языка.
            if Lang.chosen != code { app.setLanguage(code) }
        } label: {
            HStack {
                Text(title)
                Spacer()
                if Lang.chosen == code {
                    Image(systemName: "checkmark.circle.fill").foregroundStyle(Color.tmBlueStrong)
                }
            }
            .frame(minHeight: 44).contentShape(Rectangle())
        }
        .accessibilityIdentifier(id)
        .accessibilityAddTraits(Lang.chosen == code ? .isSelected : [])
    }

    private func saveAddress() {
        addressError = Validation.serverURL(address)
        guard addressError == nil else { return }
        app.services.session.serverURL = address
        hideKeyboard()
        saved = true
    }
}
