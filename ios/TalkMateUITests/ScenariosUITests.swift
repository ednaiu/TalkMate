import XCTest

/// Сценарии использования на подменённом сервере. Идентификаторы элементов совпадают с Android-версией.
class UITestBase: XCTestCase {
    var app: XCUIApplication!

    override func setUp() {
        continueAfterFailure = false
    }

    func launch(_ environment: [String: String] = [:]) {
        app = XCUIApplication()
        app.launchArguments = ["-uiTesting", "-AppleLanguages", "(ru)"]
        app.launchEnvironment = environment
        app.launch()
    }

    func openSignUp() {
        tap("btnRegistration")
        tap("btnRegistration")
        tap("btnRegistration")
    }

    func launchLoggedIn(_ environment: [String: String] = [:]) {
        launch(environment.merging(["FAKE_LOGGED_IN": "1"]) { $1 })
    }

    func text(_ id: String) -> XCUIElement { app.staticTexts[id] }
    func button(_ id: String) -> XCUIElement { app.buttons[id] }

    func shown(_ element: XCUIElement, file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertTrue(element.waitForExistence(timeout: 5), "нет элемента \(element)", file: file, line: line)
    }

    func type(_ id: String, _ value: String, secure: Bool = false) {
        // Поля пароля в тестовом режиме обычные: симулятор теряет текст, набранный в защищённое поле.
        let field = app.textFields[id]
        shown(field)
        field.tap()
        field.typeText(value)
        // Убираем клавиатуру, иначе она закрывает следующие поля и кнопки.
        let done = app.buttons["btnKeyboardDone"]
        if done.waitForExistence(timeout: 2) { done.tap() }
    }

    func assertLabel(_ id: String, _ expected: String, file: StaticString = #filePath, line: UInt = #line) {
        let element = text(id)
        shown(element, file: file, line: line)
        XCTAssertEqual(element.label, expected, file: file, line: line)
    }

    func tap(_ id: String) {
        let element = button(id)
        shown(element)
        element.tap()
    }
}

final class AuthUITests: UITestBase {
    func testWelcomeShowsLogoAndBothButtons() {
        launch()
        assertLabel("tvTalk", "Talk")
        assertLabel("tvMate", "Mate")
        XCTAssertEqual(button("btnLogin").label, "Войти")
        XCTAssertEqual(button("btnRegistration").label, "Начать репетицию")
    }

    func testLoginButtonOpensLoginForm() {
        launch()
        tap("btnLogin")
        assertLabel("tvHello", "Войди, чтобы продолжить тренировки")
        shown(app.textFields["etEmail"])
        shown(app.textFields["etPassword"])
    }

    func testRegistrationButtonOpensSignUpForm() {
        launch()
        openSignUp()
        assertLabel("tvHello", "Сохраняй результаты тренировок")
        assertLabel("tvTitle", "Создать аккаунт")
        XCTAssertEqual(app.textFields["etName"].placeholderValue, "Как к тебе обращаться")
        XCTAssertEqual(app.textFields["etPhone"].placeholderValue, "+7 …")
        XCTAssertEqual(app.textFields["etBirthDate"].placeholderValue, "ДД.ММ.ГГГГ")
    }

    func testLoggedInUserSkipsWelcome() {
        launchLoggedIn()
        assertLabel("tvWelcomeMessage", "Привет, Эдна!")
    }

    /// Сценарий из спецификации: регистрация нового пользователя.
    func testRegistration() {
        launch()
        openSignUp()
        type("etName", "John Doe")
        type("etEmail", "johndoe@example.com")
        type("etPassword", "password", secure: true)
        tap("btnRegister")
        assertLabel("tvWelcomeMessage", "Привет, John Doe!")
    }

    func testRegistrationRequiresName() {
        launch()
        openSignUp()
        type("etEmail", "new@itmo.ru")
        type("etPassword", "password", secure: true)
        tap("btnRegister")
        assertLabel("tvError", "Введите имя")
    }

    func testRegistrationRejectsBadEmailAndShortPassword() {
        launch()
        openSignUp()
        type("etName", "Edna")
        type("etEmail", "not-an-email")
        type("etPassword", "123", secure: true)
        tap("btnRegister")
        assertLabel("tvError", "Введите корректный email")
        type("etEmail", "@itmo.ru")
        tap("btnRegister")
        assertLabel("tvError", "Пароль должен быть не короче 6 символов")
    }

    func testRegistrationRejectsBadBirthDate() {
        launch()
        openSignUp()
        type("etName", "Edna")
        type("etEmail", "new@itmo.ru")
        type("etPassword", "password", secure: true)
        type("etBirthDate", "31.02.2001")
        tap("btnRegister")
        assertLabel("tvError", "Дата рождения в формате ДД.ММ.ГГГГ")
    }

    func testRegistrationWithTakenEmailShowsServerMessage() {
        launch()
        openSignUp()
        type("etName", "Edna")
        type("etEmail", "edna@itmo.ru")
        type("etPassword", "password", secure: true)
        tap("btnRegister")
        assertLabel("tvError", "Пользователь с таким email уже зарегистрирован")
        XCTAssertTrue(button("btnRegister").isEnabled)
    }

    func testGenderToggle() {
        launch()
        openSignUp()
        tap("btnFemale")
        XCTAssertTrue(button("btnFemale").isSelected)
        XCTAssertFalse(button("btnMale").isSelected)
        tap("btnMale")
        XCTAssertTrue(button("btnMale").isSelected)
        XCTAssertFalse(button("btnFemale").isSelected)
    }

    func testLoginWithCorrectPasswordOpensHome() {
        launch()
        tap("btnLogin")
        type("etEmail", "edna@itmo.ru")
        type("etPassword", "secret1", secure: true)
        tap("btnLogin")
        assertLabel("tvWelcomeMessage", "Привет, Эдна!")
    }

    func testLoginWithWrongPasswordShowsError() {
        launch()
        tap("btnLogin")
        type("etEmail", "edna@itmo.ru")
        type("etPassword", "wrong-password", secure: true)
        tap("btnLogin")
        assertLabel("tvError", "Неверный email или пароль")
    }

    func testLoginRequiresEmail() {
        launch()
        tap("btnLogin")
        type("etPassword", "secret1", secure: true)
        tap("btnLogin")
        assertLabel("tvError", "Введите email")
    }

    func testLoginWithoutNetworkShowsMessageAndAllowsRetry() {
        launch(["FAKE_FAIL": "network"])
        tap("btnLogin")
        type("etEmail", "edna@itmo.ru")
        type("etPassword", "secret1", secure: true)
        tap("btnLogin")
        assertLabel("tvError", "Нет связи с сервером. Проверьте подключение к сети")
        tap("btnLogin")
        assertLabel("tvWelcomeMessage", "Привет, Эдна!")
    }
}

final class RecoveryUITests: UITestBase {
    private func openRecovery(email: String = "edna@itmo.ru", _ environment: [String: String] = [:]) {
        launch(environment)
        tap("btnLogin")
        if !email.isEmpty { type("etEmail", email) }
        tap("tvForgot")
    }

    func testForgotLinkOpensRecoveryWithTypedEmail() {
        openRecovery()
        assertLabel("tvHello", "Забыли пароль?\nСейчас восстановим")
        XCTAssertEqual(app.textFields["etEmail"].value as? String, "edna@itmo.ru")
        XCTAssertFalse(app.textFields["etCode"].exists)
        XCTAssertEqual(button("btnSendCode").label, "Получить код")
    }

    func testRecoveryRequiresEmail() {
        openRecovery(email: "")
        tap("btnSendCode")
        assertLabel("tvError", "Введите email")
        XCTAssertFalse(app.textFields["etCode"].exists)
    }

    func testRequestingCodeShowsSecondStep() {
        openRecovery()
        tap("btnSendCode")
        shown(app.textFields["etCode"])
        shown(app.textFields["etNewPassword"])
        XCTAssertTrue(text("tvInfo").label.contains("edna@itmo.ru"))
        XCTAssertFalse(app.textFields["etEmail"].isEnabled)
        XCTAssertEqual(button("btnSendCode").label, "Отправить код ещё раз")
    }

    func testWrongCodeShowsError() {
        openRecovery()
        tap("btnSendCode")
        type("etCode", "000000")
        type("etNewPassword", "newpass1", secure: true)
        tap("btnResetPassword")
        assertLabel("tvError", "Неверный или просроченный код. Запросите новый")
        XCTAssertTrue(button("btnResetPassword").isEnabled)
    }

    func testCodeAndPasswordAreCheckedBeforeSending() {
        openRecovery()
        tap("btnSendCode")
        type("etCode", "123")
        type("etNewPassword", "newpass1", secure: true)
        tap("btnResetPassword")
        assertLabel("tvError", "Введите код из шести цифр")
    }

    func testCorrectCodeChangesPasswordAndOpensHome() {
        openRecovery()
        tap("btnSendCode")
        type("etCode", "123456")
        type("etNewPassword", "newpass1", secure: true)
        tap("btnResetPassword")
        assertLabel("tvWelcomeMessage", "Привет, Эдна!")
    }

    func testRecoveryWithoutNetworkShowsMessage() {
        openRecovery(["FAKE_FAIL": "network"])
        tap("btnSendCode")
        assertLabel("tvError", "Нет связи с сервером. Проверьте подключение к сети")
        tap("btnSendCode")
        shown(app.textFields["etCode"])
    }
}

final class HomeUITests: UITestBase {
    func testHomeShowsThreeSections() {
        launchLoggedIn()
        assertLabel("tvMate", "Mate")
        assertLabel("tvCaption", "ТРЕНИРОВКА РЕЧИ")
        assertLabel("tvHomeTitle", "Говори\nувереннее")
        shown(app.staticTexts["Запиши выступление и узнай, как улучшить свою речь"])
        XCTAssertEqual(button("btnStartTraining").label, "Начать тренировку  →")
        XCTAssertTrue(button("cardArticles").label.contains("Статьи"))
        XCTAssertTrue(button("cardArticles").label.contains("Советы по публичным выступлениям"))
        XCTAssertTrue(button("cardStats").label.contains("Мой прогресс"))
    }

    func testTrainingCardItselfOpensRecorder() {
        launchLoggedIn()
        shown(text("tvHomeTitle"))
        text("tvHomeTitle").tap()
        assertLabel("tvTitle", "ЗАПИСЬ")
    }

    func testCardsOpenSectionsAndBackReturnsHome() {
        launchLoggedIn()
        tap("btnStartTraining")
        assertLabel("tvTitle", "ЗАПИСЬ")
        tap("btnBack")
        tap("cardArticles")
        assertLabel("tvTitle", "СТАТЬИ")
        tap("btnBack")
        tap("cardStats")
        assertLabel("tvTitle", "Stats")
        tap("btnBack")
        shown(button("btnStartTraining"))
    }

    func testBackFromLoginAndSignUpReturnsToWelcome() {
        launch()
        tap("btnLogin")
        tap("btnBack")
        shown(text("tvMate"))
        openSignUp()
        tap("btnBack")
        shown(text("tvMate"))
    }

    func testProfileShowsUserAndLogoutReturnsToWelcome() {
        launchLoggedIn()
        tap("btnProfile")
        assertLabel("tvName", "Эдна Юсупова")
        assertLabel("tvCount", "12")
        assertLabel("tvCountCaption", "тренировок")
        assertLabel("tvTempoValue", "142")
        // Снимок личного кабинета для просмотра глазами; лежит во временной папке симулятора.
        try? XCUIScreen.main.screenshot().pngRepresentation.write(to: URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("talkmate_profile.png"))
        tap("btnSettings")
        shown(text("settingsTitle"))
        app.swipeUp()
        tap("btnLogout")
        app.buttons["Выйти"].tap()
        shown(button("btnRegistration"))
    }

    func testTrainingFromTheListOpensItsResults() {
        launchLoggedIn()
        tap("navTrainings")
        assertLabel("tvTitle", "Тренировки")
        tap("training6")
        shown(text("tvRate"))
    }

    func testArticleListAndArticleText() {
        launchLoggedIn()
        tap("cardArticles")
        for title in ["Жестикуляция и движение", "Подготовка на площадке", "Использование презентаций", "Разогрев"] {
            shown(app.buttons[title])
        }
        app.buttons["Жестикуляция и движение"].tap()
        assertLabel("tvArticleTitle", "Жестикуляция и движение")
        shown(text("tvArticleContent"))
        XCTAssertTrue(text("tvArticleContent").label.contains("толкание, вытягивание, подъём, бросание и разрывание."))
        XCTAssertFalse(text("tvArticleContent").label.contains("**"))
        tap("btnBack")
        shown(app.buttons["Разогрев"])
    }

    func testArticlesWithoutNetworkShowOoopsAndRetryLoadsList() {
        launchLoggedIn(["FAKE_FAIL": "network"])
        tap("cardArticles")
        assertLabel("tvOoops", "Ooops…")
        assertLabel("tvErrorMessage", "Нет связи с сервером. Проверьте подключение к сети")
        tap("btnRetry")
        shown(app.buttons["Разогрев"])
    }

    func testBackArrowOnErrorScreenLeavesBrokenScreen() {
        launchLoggedIn(["FAKE_FAIL": "network"])
        tap("cardArticles")
        shown(text("tvOoops"))
        tap("btnErrorBack")
        shown(button("btnStartTraining"))
    }

    func testStatsWithoutRecordingsShowHint() {
        launchLoggedIn()
        tap("cardStats")
        shown(text("tvEmpty"))
        XCTAssertTrue(text("tvEmpty").label.contains("запишете первое выступление"))
    }

    func testStatsDrawChartsFromHistory() {
        launchLoggedIn(["FAKE_STATS": "1"])
        tap("cardStats")
        let rate = app.descendants(matching: .any)["chartRate"]
        shown(rate)
        XCTAssertEqual(rate.label, "Оценка скорости (слов/мин): 205, 196, 155")
        XCTAssertEqual(app.descendants(matching: .any)["chartFillers"].label, "Количество слов-заполнителей: 10, 5, 2")
        app.swipeUp()
        app.swipeUp()
        XCTAssertEqual(app.descendants(matching: .any)["chartClarity"].label, "Чёткость речи, %: 81, 82, 83")
        XCTAssertFalse(text("tvEmpty").exists)
    }

    func testExpiredSessionSendsUserToWelcome() {
        launchLoggedIn(["FAKE_FAIL": "unauthorized"])
        tap("cardArticles")
        shown(button("btnRegistration"))
        assertLabel("tvNotice", "Сессия истекла, войдите снова")
    }
}

final class TrainingUITests: UITestBase {
    private func openRecorder(_ environment: [String: String] = [:]) {
        launchLoggedIn(environment)
        tap("btnStartTraining")
    }

    func testRecorderStartsIdle() {
        openRecorder()
        assertLabel("tvTimer", "00:00.000")
        XCTAssertFalse(button("btnStop").isEnabled)
        XCTAssertFalse(button("btnAnalyze").isEnabled)
        XCTAssertEqual(button("btnRecordPause").label, "Начать запись")
    }

    func testStartPauseResumeStop() {
        openRecorder()
        tap("btnRecordPause")
        assertLabel("tvHint", "Идёт запись")
        assertLabel("tvTimer", "02:20.000")
        XCTAssertTrue(button("btnStop").isEnabled)
        XCTAssertTrue(button("btnAnalyze").isEnabled)
        XCTAssertEqual(button("btnRecordPause").label, "Пауза")
        tap("btnRecordPause")
        assertLabel("tvHint", "Запись на паузе")
        XCTAssertEqual(button("btnRecordPause").label, "Продолжить запись")
        tap("btnRecordPause")
        assertLabel("tvHint", "Идёт запись")
        tap("btnStop")
        assertLabel("tvHint", "Запись готова. Нажмите «Анализ»")
        XCTAssertFalse(button("btnStop").isEnabled)
        XCTAssertTrue(button("btnAnalyze").isEnabled)
    }

    func testTooShortRecordingIsNotSent() {
        openRecorder(["FAKE_SHORT": "1"])
        tap("btnRecordPause")
        tap("btnAnalyze")
        XCTAssertTrue(text("tvHint").label.contains("Запись слишком короткая"))
        assertLabel("tvTimer", "00:00.000")
    }

    func testMicrophoneFailureAndDenialAreExplained() {
        openRecorder(["FAKE_MIC_FAIL": "1"])
        tap("btnRecordPause")
        assertLabel("tvHint", "Не удалось включить микрофон")
        XCTAssertFalse(button("btnAnalyze").isEnabled)
        app.terminate()
        openRecorder(["FAKE_MIC_DENIED": "1"])
        tap("btnRecordPause")
        XCTAssertTrue(text("tvHint").label.contains("Без доступа к микрофону"))
    }

    /// Основной сценарий: записать речь, получить оценки и рекомендации. Значения как в макете.
    func testRecordAnalyzeAndSeeResults() {
        openRecorder()
        tap("btnRecordPause")
        tap("btnStop")
        tap("btnAnalyze")
        assertLabel("tvResultsTitle", "Разбор репетиции")
        assertLabel("tvRecommendationsTitle", "Что попробовать")
        assertLabel("tvRate", "250 сл/мин")
        app.swipeUp()
        tap("btnAllMetrics")
        assertLabel("tvVolume", "тихая")
        assertLabel("tvMonotony", "разнообразная")
        XCTAssertFalse(text("tvEmotion").exists)
        assertLabel("tvClarity", "средняя")
        assertLabel("tvFillers", "5 слов")
        assertLabel("tvFillerWords", "Чаще всего: «ну», «вот»")
        assertLabel("tvMainIdea", "Сегодня я расскажу о нашем приложении.")
        assertLabel("tvKeywords", "Ключевые слова: приложение, речь")
        assertLabel("tvStructure", "частичная")
        XCTAssertTrue(text("tvStructureSummary").label.contains("заключения нет"))
        app.swipeUp()
        XCTAssertTrue(text("tvRecText").label.contains("Запиши одну фразу"))
        tap("btnBack")
        shown(button("btnStartTraining"))
    }

    func testTranscriptIsHiddenUntilRequested() {
        openRecorder()
        tap("btnRecordPause")
        tap("btnAnalyze")
        shown(text("tvResultsTitle"))
        app.swipeUp()
        XCTAssertFalse(text("tvTranscript").exists)
        XCTAssertEqual(button("btnTranscript").label, "Показать расшифровку")
        tap("btnTranscript")
        // Над первой фразой пометка о темпе, над второй об окраске; текст фраз идёт под пометками.
        assertLabel("tvTranscript", "быстро, 212 сл/мин\nНу, вот, сегодня я расскажу\n\nневнятно, 62%  ·  грусть\nо нашем приложении.")
        XCTAssertTrue(text("tvTranscriptLegend").label.contains("Заполнителей: 2; фраза с темпом вне нормы: 1; невнятная фраза: 1; фраза с отрицательной окраской: 1"))
        XCTAssertEqual(button("btnTranscript").label, "Скрыть расшифровку")
        tap("btnTranscript")
        XCTAssertFalse(text("tvTranscript").exists)
    }

    func testAnalysisFailureShowsOoopsAndRetrySucceeds() {
        openRecorder(["FAKE_FAIL": "server"])
        tap("btnRecordPause")
        tap("btnAnalyze")
        assertLabel("tvErrorMessage", "Сервис распознавания речи недоступен")
        tap("btnRetry")
        shown(text("tvResultsTitle"))
    }

    func testAnalysisFailureBackKeepsRecording() {
        openRecorder(["FAKE_FAIL": "server"])
        tap("btnRecordPause")
        tap("btnAnalyze")
        shown(text("tvOoops"))
        tap("btnErrorBack")
        assertLabel("tvHint", "Запись готова. Нажмите «Анализ»")
        tap("btnAnalyze")
        shown(text("tvResultsTitle"))
    }

    func testResultsForMonotoneSpeechAndRecordAgain() {
        openRecorder(["FAKE_MONOTONE": "1"])
        tap("btnRecordPause")
        tap("btnAnalyze")
        assertLabel("tvRate", "96 сл/мин")
        app.swipeUp()
        tap("btnAllMetrics")
        assertLabel("tvVolume", "громкая")
        assertLabel("tvMonotony", "мало изменений")
        XCTAssertFalse(text("tvEmotion").exists)
        assertLabel("tvClarity", "не определена")
        assertLabel("tvFillers", "1 слово")
        XCTAssertFalse(text("tvFillerWords").exists)
        XCTAssertFalse(text("tvMainIdea").exists)     // сервер не прислал содержание
        // Сервер не прислал текст: кнопки расшифровки нет.
        XCTAssertFalse(button("btnTranscript").exists)
        for _ in 0..<5 { app.swipeDown() }
        tap("btnAgain")
        assertLabel("tvTitle", "ЗАПИСЬ")
        assertLabel("tvTimer", "00:00.000")
    }
}
