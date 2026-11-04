import XCTest

/// Экспорт реальных кадров iOS для документации. Данные и авторизация — FakeApi.
final class ScreenshotCaptureUITests: UITestBase {
    func testCaptureWelcome() throws {
        launch()
        shown(button("btnRegistration"))
        XCTAssertTrue(button("btnRegistration").isHittable)
        XCTAssertTrue(button("btnLogin").isHittable)
        try capture("20_welcome_ios")
    }

    func testWelcomeWithLargeText() throws {
        app = XCUIApplication()
        app.launchArguments = ["-uiTesting", "-AppleLanguages", "(ru)",
                               "-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityXXXL"]
        app.launch()
        shown(button("btnRegistration"))
        for _ in 0..<4 {
            if button("btnRegistration").isHittable { break }
            app.swipeUp()
        }
        XCTAssertTrue(button("btnRegistration").isHittable)
        for _ in 0..<4 {
            if button("btnLogin").isHittable { break }
            app.swipeUp()
        }
        try capture("21_welcome_large_text_ios")
        XCTAssertTrue(button("btnLogin").isHittable)
    }

    func testCaptureOnboardingRussian() throws {
        launch()
        try captureOnboarding(prefix: "24_onboarding_ru")
    }

    func testCaptureOnboardingEnglish() throws {
        app = XCUIApplication()
        app.launchArguments = ["-uiTesting", "-AppleLanguages", "(en)", "-appLanguage", "en"]
        app.launch()
        shown(button("btnRegistration"))
        XCTAssertEqual(button("btnRegistration").label, "Start rehearsing")
        try captureOnboarding(prefix: "25_onboarding_en")
    }

    func testOnboardingBackSkipAndLegalDocuments() throws {
        launch()
        tap("btnRegistration")
        shown(button("onboardingBack"))
        tap("onboardingBack")
        XCTAssertEqual(button("btnRegistration").label, "Начать репетицию")
        tap("onboardingSkip")
        shown(app.textFields["etName"])
        tap("btnBack")
        let terms = app.links.matching(NSPredicate(format: "label CONTAINS[c] %@", "условия")).firstMatch
        if !terms.isHittable { app.swipeUp() }
        shown(terms)
        terms.tap()
        shown(text("legalDraftNotice"))
        shown(app.staticTexts["Условия использования Talk Mate"])
        try capture("26_legal_terms_draft_ios")
        tap("closeLegalDocument")
        tap("btnRegistration")
        tap("btnRegistration")
        tap("btnRegistration")
        shown(app.textFields["etName"])
    }

    func testOnboardingSwipeNavigation() {
        launch()
        app.swipeLeft()
        shown(button("onboardingBack"))
        app.swipeRight()
        XCTAssertEqual(button("btnRegistration").label, "Начать репетицию")
    }

    private func captureOnboarding(prefix: String) throws {
        for index in 1...3 {
            shown(button("btnRegistration"))
            XCTAssertTrue(button("btnRegistration").isHittable)
            try capture("\(prefix)_\(index)")
            if index < 3 { tap("btnRegistration") }
        }
    }

    func testCaptureResultsTypography() throws {
        launchLoggedIn()
        tap("navTrainings")
        tap("training6")
        shown(text("tvResultsTitle"))
        XCTAssertTrue(button("btnAgain").isHittable)
        XCTAssertFalse(text("tvVolume").exists)
        try capture("28_results_review_ios")
        app.swipeUp()
        tap("btnAllMetrics")
        shown(text("tvVolume"))
        try capture("29_results_details_ios")
    }

    func testResultsEnglishAndLargeText() throws {
        app = XCUIApplication()
        app.launchArguments = ["-uiTesting", "-AppleLanguages", "(en)", "-appLanguage", "en",
                               "-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityXXXL"]
        app.launchEnvironment = ["FAKE_LOGGED_IN": "1"]
        app.launch()
        tap("navTrainings")
        tap("training6")
        shown(text("tvResultsTitle"))
        XCTAssertEqual(text("tvResultsTitle").label, "Rehearsal review")
        for _ in 0..<6 {
            if button("btnAgain").isHittable { break }
            app.swipeUp()
        }
        XCTAssertTrue(button("btnAgain").isHittable)
        try capture("30_results_large_text_en_ios")
        for _ in 0..<10 {
            if button("btnAllMetrics").isHittable { break }
            app.swipeUp()
        }
        tap("btnAllMetrics")
        shown(text("tvVolume"))
        XCTAssertEqual(text("tvVolume").label, "quiet")
        for _ in 0..<10 {
            if text("tvVolume").isHittable { break }
            app.swipeUp()
        }
        XCTAssertTrue(text("tvVolume").isHittable)
        try capture("31_results_details_large_text_en_ios")
        for _ in 0..<10 {
            if button("btnAgain").isHittable { break }
            app.swipeDown()
        }
        tap("btnAgain")
        shown(button("btnRecordPause"))
    }

    func testCaptureExistingScreens() throws {
        launchLoggedIn()
        tap("btnProfile")
        shown(text("tvName"))
        try capture("17_profile_ios")

        tap("btnSettings")
        shown(text("settingsTitle"))
        try capture("16_settings_ios")

        tap("btnBack")
        tap("navTrainings")
        shown(button("training6"))
        try capture("18_trainings_ios")

        tap("navHome")
        tap("btnStartTraining")
        shown(button("btnRecordPause"))
        try capture("19_record_ios")
    }

    func testExportAllAuthScreens() throws {
        exportLaunch()
        shown(button("btnRegistration"))
        try capture("all_01_onboarding_1")
        let terms = app.links.matching(NSPredicate(format: "label CONTAINS[c] %@", "Terms")).firstMatch
        terms.tap()
        shown(text("legalDraftNotice"))
        try capture("all_04_terms_draft")
        tap("closeLegalDocument")
        let privacy = app.links.matching(NSPredicate(format: "label CONTAINS[c] %@", "Privacy")).firstMatch
        privacy.tap()
        shown(text("legalDraftNotice"))
        try capture("all_05_privacy_draft")
        tap("closeLegalDocument")
        tap("btnRegistration")
        try capture("all_02_onboarding_2")
        tap("btnRegistration")
        try capture("all_03_onboarding_3")
        tap("btnRegistration")
        shown(app.textFields["etName"])
        try capture("all_06_signup_top")
        app.swipeUp()
        try capture("all_07_signup_bottom")
        tap("btnBack")
        tap("btnLogin")
        shown(app.textFields["etEmail"])
        try capture("all_08_login")
        tap("tvForgot")
        shown(button("btnSendCode"))
        try capture("all_09_recovery_email")
        type("etEmail", "demo@example.com")
        tap("btnSendCode")
        shown(app.textFields["etCode"])
        try capture("all_10_recovery_code")
    }

    func testExportAllMainScreens() throws {
        exportLaunch(loggedIn: true, ["FAKE_STATS": "1"])
        shown(button("btnStartTraining"))
        try capture("all_11_home")
        tap("btnProfile")
        shown(text("tvName"))
        try capture("all_12_profile_top")
        app.swipeUp()
        try capture("all_13_profile_bottom")
        tap("btnSettings")
        shown(text("settingsTitle"))
        try capture("all_14_settings_top")
        app.swipeUp()
        try capture("all_15_settings_bottom")
        tap("btnBack")
        tap("navTrainings")
        shown(button("training6"))
        try capture("all_16_trainings")
        tap("navHome")
        tap("cardArticles")
        shown(app.buttons["Gestures and movement"])
        try capture("all_17_articles")
        for (index, title) in ["Gestures and movement", "Preparing at the venue", "Using slides", "Warm-up"].enumerated() {
            app.buttons[title].tap()
            shown(text("tvArticleContent"))
            try capture("all_\(18 + index)_article_\(index + 1)")
            tap("btnBack")
        }
        tap("btnBack")
        tap("cardStats")
        shown(text("tvTitle"))
        // Графики появляются после завершения загрузки.
        shown(app.descendants(matching: .any)["chartRate"])
        try capture("all_22_stats_top")
        app.swipeUp()
        try capture("all_23_stats_middle")
        app.swipeUp()
        app.swipeUp()
        try capture("all_38_stats_bottom")
    }

    func testExportAllRecordingScreens() throws {
        exportLaunch(loggedIn: true)
        tap("btnStartTraining")
        shown(button("btnRecordPause"))
        try capture("all_24_record_idle")
        tap("btnRecordPause")
        try capture("all_25_record_active")
        tap("btnRecordPause")
        try capture("all_26_record_paused")
        tap("btnStop")
        try capture("all_27_record_ready")
        tap("btnAnalyze")
        shown(text("tvResultsTitle"))
        try capture("all_28_results_summary")
        reveal("btnAllMetrics")
        try capture("all_29_results_metrics")
        tap("btnAllMetrics")
        app.swipeUp()
        try capture("all_30_results_details")
        reveal("btnTranscript")
        try capture("all_31_results_content")
        tap("btnTranscript")
        shown(text("tvTranscript"))
        app.swipeUp()
        try capture("all_32_results_transcript")
    }

    func testExportAllSlidesAndStates() throws {
        exportLaunch(loggedIn: true, ["FAKE_SLIDES": "1"])
        tap("btnStartTraining")
        shown(text("tvSlideNumber"))
        try capture("all_33_record_with_slides")
        tap("btnNextSlide")
        try capture("all_34_slide_viewer")
        tap("btnRecordPause")
        reveal("btnAnalyze")
        tap("btnAnalyze")
        shown(text("tvResultsTitle"))
        reveal("btnTranscript")
        try capture("all_35_results_slides")

        exportLaunch(loggedIn: true)
        tap("cardStats")
        shown(text("tvEmpty"))
        try capture("all_36_stats_empty")

        exportLaunch(loggedIn: true, ["FAKE_FAIL": "network"])
        tap("cardArticles")
        shown(text("tvOoops"))
        try capture("all_37_connection_error")
    }

    private func exportLaunch(loggedIn: Bool = false, _ environment: [String: String] = [:]) {
        app = XCUIApplication()
        app.launchArguments = ["-uiTesting", "-AppleLanguages", "(en)", "-appLanguage", "en"]
        app.launchEnvironment = environment
        if loggedIn { app.launchEnvironment["FAKE_LOGGED_IN"] = "1" }
        app.launch()
    }

    private func reveal(_ id: String) {
        for _ in 0..<8 {
            if button(id).isHittable { return }
            app.swipeUp()
        }
        XCTAssertTrue(button(id).isHittable)
    }

    private func capture(_ name: String) throws {
        // Дождаться SwiftUI-переходов и окончания прокрутки перед нативным снимком.
        Thread.sleep(forTimeInterval: 0.7)
        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
        let directory = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("talkmate-docs-screens", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let target = directory.appendingPathComponent(name + ".png")
        try screenshot.pngRepresentation.write(to: target)
        print("DOCS_SCREENSHOT: \(target.path)")
    }
}
