import SwiftUI

/// Общий каркас экранов с формой: розовая шапка с кнопкой «назад» и приветствием, белый лист с полями.
struct FormScreen<Content: View>: View {
    let hello: String
    let title: String
    var topGap: CGFloat = 40
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            BackButton().padding(.leading, 24).padding(.top, 8)
            HelloText(text: hello).padding(.top, 12).padding(.bottom, topGap)
            Sheet {
                ScrollView {
                    VStack(spacing: 14) {
                        Text(title).font(.display(24)).foregroundStyle(Color.tmInk).padding(.bottom, 22).accessibilityIdentifier("tvTitle")
                        content
                    }
                    .padding(.horizontal, 36)
                    .padding(.top, 48)
                    .padding(.bottom, 32)
                }
                .scrollDismissesKeyboard(.interactively)
            }
        }
        .background(Color.tmPink.ignoresSafeArea())
        // У цифровой клавиатуры нет клавиши ввода, поэтому над клавиатурой всегда есть кнопка «Готово».
        .toolbar {
            ToolbarItemGroup(placement: .keyboard) {
                Spacer()
                Button(L("Готово", "Done")) { hideKeyboard() }.accessibilityIdentifier("btnKeyboardDone")
            }
        }
    }
}

/// Каркас экранов входа и регистрации: иллюстрация на розовом фоне, белая карточка с формой и ссылка под ней.
struct AuthScreen<Content: View, Footer: View>: View {
    let title: String
    let subtitle: String
    var artWidth: CGFloat = 230
    @ViewBuilder var content: Content
    @ViewBuilder var footer: Footer

    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                BackButton().frame(maxWidth: .infinity, alignment: .leading).padding(.leading, 4).padding(.top, 8)
                WelcomeArt(blob: .tmPinkShape).frame(width: artWidth)
                Text("Talk Mate").font(.wordmark(16)).foregroundStyle(Color.tmSubtitle).padding(.top, 4)
                VStack(alignment: .leading, spacing: 0) {
                    Text(title).font(.interface(30, weight: .medium)).foregroundStyle(Color.tmInk).accessibilityIdentifier("tvTitle")
                    Text(subtitle).font(.interface(16)).foregroundStyle(Color.tmGreyTitle).padding(.top, 6)
                        .accessibilityIdentifier("tvHello")
                    content
                }
                .padding(26)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: 32).fill(Color.tmCard))
                .padding(.top, 18)
                footer.padding(.top, 16)
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 24)
        }
        .scrollDismissesKeyboard(.interactively)
        .background(Color.tmPink.ignoresSafeArea())
        // У цифровой клавиатуры нет клавиши ввода, поэтому над клавиатурой всегда есть кнопка «Готово».
        .toolbar {
            ToolbarItemGroup(placement: .keyboard) {
                Spacer()
                Button(L("Готово", "Done")) { hideKeyboard() }.accessibilityIdentifier("btnKeyboardDone")
            }
        }
    }
}

/// Строка под карточкой: вопрос и ссылка на соседний экран.
struct AuthSwitch: View {
    let question: String
    let link: String
    let id: String
    let action: () -> Void

    var body: some View {
        HStack(spacing: 6) {
            Text(question).font(.interface(17)).foregroundStyle(Color.tmSubtitle)
            Button(link, action: action)
                .font(.interface(17, weight: .semibold)).foregroundStyle(Color.tmBlueStrong)
                .frame(minHeight: 44)
                .accessibilityIdentifier(id)
        }
    }
}

struct LoginView: View {
    @EnvironmentObject private var app: AppState
    @State private var email = ""
    @State private var password = ""
    @State private var error: String?
    @State private var busy = false

    var body: some View {
        AuthScreen(title: L("С возвращением!", "Welcome back!"), subtitle: L("Войди, чтобы продолжить тренировки", "Log in to continue practicing")) {
            AuthField(label: L("Электронная почта", "Email"), hint: "name@example.com", text: $email, id: "etEmail",
                      keyboard: .emailAddress, contentType: .username)
            AuthField(label: L("Пароль", "Password"), hint: L("Введи пароль", "Enter your password"), text: $password, id: "etPassword", secure: true, contentType: .password)
            Button(L("Забыли пароль?", "Forgot your password?")) {
                app.path.append(.resetPassword(email: email.trimmingCharacters(in: .whitespaces)))
            }
            .font(.interface(16)).foregroundStyle(Color.tmBlueStrong)
            .frame(maxWidth: .infinity, minHeight: 44, alignment: .trailing)
            .accessibilityIdentifier("tvForgot")
            FormError(text: error)
            Button(L("Войти", "Log in"), action: submit)
                .buttonStyle(StrongButtonStyle()).disabled(busy).padding(.top, 12)
                .accessibilityIdentifier("btnLogin")
            if busy { ProgressView().tint(.tmBlueStrong).frame(maxWidth: .infinity).padding(.top, 10) }
        } footer: {
            AuthSwitch(question: L("Нет аккаунта?", "No account yet?"), link: L("Создать аккаунт", "Create account"), id: "tvCreateAccount") {
                app.path.removeLast()
                app.path.append(.signUp)
            }
        }
    }

    private func submit() {
        let mail = email.trimmingCharacters(in: .whitespaces)
        if let problem = Validation.email(mail) ?? (password.isEmpty ? L("Введите пароль", "Enter a password") : nil) {
            error = problem
            return
        }
        error = nil
        busy = true
        Task {
            switch await app.call({ try await $0.login(email: mail, password: password) }) {
            case .success(let result): app.signedIn(result)
            case .failure(let failure): error = failure.message
            }
            busy = false
        }
    }
}

struct SignUpView: View {
    @EnvironmentObject private var app: AppState
    @State private var name = ""
    @State private var email = ""
    @State private var password = ""
    @State private var phone = ""
    @State private var birth = ""
    @State private var gender: String?
    @State private var datePickerShown = false
    @State private var pickedDate = Calendar.current.date(byAdding: .year, value: -20, to: Date()) ?? Date()
    @State private var error: String?
    @State private var busy = false

    var body: some View {
        AuthScreen(title: L("Создать аккаунт", "Create account"), subtitle: L("Сохраняй результаты тренировок", "Keep your practice results"), artWidth: 190) {
            AuthField(label: L("Имя", "Name"), hint: L("Как к тебе обращаться", "What should we call you"), text: $name, id: "etName", contentType: .name, capitalization: .words)
            AuthField(label: L("Электронная почта", "Email"), hint: "name@example.com", text: $email, id: "etEmail",
                      keyboard: .emailAddress, contentType: .emailAddress)
            AuthField(label: L("Пароль", "Password"), hint: L("Придумай пароль", "Create a password"), text: $password, id: "etPassword", secure: true, contentType: .newPassword)
            AuthField(label: L("Телефон", "Phone"), hint: "+7 …", text: $phone, id: "etPhone", keyboard: .phonePad, contentType: .telephoneNumber)
            AuthField(label: L("Дата рождения", "Date of birth"), hint: L("ДД.ММ.ГГГГ", "DD.MM.YYYY"), text: $birth, id: "etBirthDate", keyboard: .numbersAndPunctuation,
                      icon: "calendar", iconLabel: L("Выбрать дату", "Pick a date")) { datePickerShown = true }
            Text(L("Пол", "Gender")).font(.interface(15, weight: .semibold)).foregroundStyle(Color.tmFieldLabel).padding(.top, 16)
            HStack(spacing: 40) {
                genderButton("female", title: L("Женский", "Female"), label: L("Женский пол", "Female"), id: "btnFemale")
                genderButton("male", title: L("Мужской", "Male"), label: L("Мужской пол", "Male"), id: "btnMale")
            }
            .frame(maxWidth: .infinity)
            FormError(text: error)
            Button(L("Создать аккаунт", "Create account"), action: submit)
                .buttonStyle(StrongButtonStyle()).disabled(busy).padding(.top, 14)
                .accessibilityIdentifier("btnRegister")
            if busy { ProgressView().tint(.tmBlueStrong).frame(maxWidth: .infinity).padding(.top, 10) }
        } footer: {
            AuthSwitch(question: L("Уже есть аккаунт?", "Already have an account?"), link: L("Войти", "Log in"), id: "tvLogin") {
                app.path.removeLast()
                app.path.append(.login)
            }
        }
        .sheet(isPresented: $datePickerShown) {
            VStack(spacing: 12) {
                DatePicker(L("Дата рождения", "Date of birth"), selection: $pickedDate, in: ...Date(), displayedComponents: .date)
                    .datePickerStyle(.graphical)
                    .environment(\.locale, Locale(identifier: "ru_RU"))
                Button(L("Готово", "Done")) {
                    // Календарь заполняет поле в том же формате, в каком дату вводят вручную.
                    let parts = Calendar.current.dateComponents([.day, .month, .year], from: pickedDate)
                    birth = String(format: "%02d.%02d.%04d", parts.day ?? 1, parts.month ?? 1, parts.year ?? 2000)
                    datePickerShown = false
                }
                .buttonStyle(StrongButtonStyle())
                .accessibilityIdentifier("btnDateDone")
            }
            .padding(20)
            .presentationDetents([.medium, .large])
        }
    }

    private func genderButton(_ value: String, title: String, label: String, id: String) -> some View {
        Button { gender = gender == value ? nil : value } label: {
            VStack(spacing: 4) {
                GenderIcon(female: value == "female")
                    .fill(gender == value ? Color.tmBlue : Color.tmBlueLight)
                    .frame(width: 30, height: 42)
                    .frame(width: 56, height: 50)
                Text(title).font(.interface(14)).foregroundStyle(Color.tmFieldLabel)
            }
            .contentShape(Rectangle())
        }
        .accessibilityLabel(label)
        .accessibilityIdentifier(id)
        .accessibilityAddTraits(gender == value ? .isSelected : [])
    }

    private func submit() {
        let trimmedName = name.trimmingCharacters(in: .whitespaces)
        let mail = email.trimmingCharacters(in: .whitespaces)
        let birthDate = birth.trimmingCharacters(in: .whitespaces)
        if let problem = Validation.name(trimmedName) ?? Validation.email(mail) ?? Validation.password(password) ?? Validation.birthDate(birthDate) {
            error = problem
            return
        }
        error = nil
        busy = true
        let request = RegisterRequest(name: trimmedName, email: mail, password: password, phone: phone,
                                      birthDate: Formatters.birthDateToISO(birthDate), gender: gender)
        Task {
            switch await app.call({ try await $0.register(request) }) {
            case .success(let result): app.signedIn(result)
            case .failure(let failure): error = failure.message
            }
            busy = false
        }
    }
}

/// Значки пола из макета: круг и треугольник, у женского основание внизу, у мужского вверху.
struct GenderIcon: Shape {
    let female: Bool

    func path(in rect: CGRect) -> Path {
        var path = Path()
        let head = rect.width * 0.3
        path.addEllipse(in: CGRect(x: rect.midX - head, y: rect.minY, width: head * 2, height: head * 2))
        let top = rect.minY + head * 2 + rect.height * 0.06
        if !female {
            path.move(to: CGPoint(x: rect.minX, y: top))
            path.addLine(to: CGPoint(x: rect.maxX, y: top))
            path.addLine(to: CGPoint(x: rect.midX, y: rect.maxY))
        } else {
            path.move(to: CGPoint(x: rect.midX, y: top))
            path.addLine(to: CGPoint(x: rect.maxX, y: rect.maxY))
            path.addLine(to: CGPoint(x: rect.minX, y: rect.maxY))
        }
        path.closeSubpath()
        return path
    }
}

/// Восстановление пароля в два шага: запросить код на почту, затем ввести код и новый пароль.
struct ResetPasswordView: View {
    @EnvironmentObject private var app: AppState
    @State private var email: String
    @State private var code = ""
    @State private var password = ""
    @State private var codeRequestedFor: String?
    @State private var error: String?
    @State private var busy = false

    init(email: String) { _email = State(initialValue: email) }

    var body: some View {
        FormScreen(hello: L("Забыли пароль?\nСейчас восстановим", "Forgot your password?\nLet us restore it"), title: "Password") {
            TMField(hint: "Email", text: $email, id: "etEmail", keyboard: .emailAddress, contentType: .username)
                .disabled(codeRequestedFor != nil)
                .opacity(codeRequestedFor == nil ? 1 : 0.6)
            if let sentTo = codeRequestedFor {
                Text(L("Если адрес \(sentTo) зарегистрирован, на него отправлено письмо с кодом из шести цифр. Код действует 15 минут.",
                       "If \(sentTo) is registered, we have sent it an email with a six-digit code. The code is valid for 15 minutes."))
                    .font(.light(16)).foregroundStyle(Color.tmGreyTitle).lineSpacing(4)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .accessibilityIdentifier("tvInfo")
                TMField(hint: L("Код из письма", "Code from the email"), text: $code, id: "etCode", keyboard: .numberPad, contentType: .oneTimeCode)
                TMField(hint: L("Новый пароль", "New password"), text: $password, id: "etNewPassword", secure: true, contentType: .newPassword)
            }
            FormError(text: error)
            if codeRequestedFor != nil {
                Button(L("Сменить пароль", "Change password"), action: changePassword)
                    .buttonStyle(FilledButtonStyle()).disabled(busy).padding(.horizontal, 8)
                    .accessibilityIdentifier("btnResetPassword")
            }
            Button(codeRequestedFor == nil ? L("Получить код", "Get the code") : L("Отправить код ещё раз", "Send the code again"), action: requestCode)
                .buttonStyle(FilledButtonStyle()).disabled(busy).padding(.horizontal, 8)
                .accessibilityIdentifier("btnSendCode")
            if busy { ProgressView().tint(.tmBlue) }
        }
    }

    private func requestCode() {
        let mail = (codeRequestedFor ?? email).trimmingCharacters(in: .whitespaces)
        if let problem = Validation.email(mail) {
            error = problem
            return
        }
        error = nil
        busy = true
        Task {
            switch await app.call({ try await $0.requestPasswordReset(email: mail) }) {
            case .success: codeRequestedFor = mail
            case .failure(let failure): error = failure.message
            }
            busy = false
        }
    }

    private func changePassword() {
        guard let mail = codeRequestedFor else { return }
        let entered = code.trimmingCharacters(in: .whitespaces)
        if let problem = Validation.code(entered) ?? Validation.password(password) {
            error = problem
            return
        }
        error = nil
        busy = true
        Task {
            switch await app.call({ try await $0.resetPassword(email: mail, code: entered, newPassword: password) }) {
            case .success(let result): app.signedIn(result)
            case .failure(let failure): error = failure.message
            }
            busy = false
        }
    }
}
