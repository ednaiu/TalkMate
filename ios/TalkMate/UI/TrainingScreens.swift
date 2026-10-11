import PDFKit
import SwiftUI
import UniformTypeIdentifiers

@MainActor
final class RecordModel: ObservableObject {
    static let minRecording: TimeInterval = 3

    @Published private(set) var state: RecorderState = .idle
    @Published private(set) var elapsed: TimeInterval = 0
    @Published private(set) var analyzing = false
    @Published private(set) var hint = L("Нажмите на кнопку записи и начните говорить", "Tap the record button and start speaking")
    @Published var error: ApiError?
    @Published private(set) var slidesName: String?
    @Published private(set) var slideImage: UIImage?
    @Published private(set) var page = 0
    @Published private(set) var pageCount = 0

    private var document: PDFDocument?
    private var marks: [SlideMark] = []

    private var slides: URL?
    private var recorder: Recorder?
    private var file: URL?
    private var ticker: Timer?
    private var handedOver = false

    func attach(_ recorder: Recorder) {
        if self.recorder == nil { self.recorder = recorder }
    }

    var active: Bool { state == .recording || state == .paused }

    /// Копирует выбранный PDF к себе: доступ к файлу по ссылке системы действует, только пока открыт выбор.
    func attachSlides(_ source: URL) {
        let scoped = source.startAccessingSecurityScopedResource()
        defer { if scoped { source.stopAccessingSecurityScopedResource() } }
        let target = FileManager.default.temporaryDirectory.appendingPathComponent("slides.pdf")
        try? FileManager.default.removeItem(at: target)
        do {
            try FileManager.default.copyItem(at: source, to: target)
        } catch {
            hint = L("Не удалось открыть файл. Выберите презентацию в формате PDF", "Could not open the file. Choose a presentation in PDF format")
            return
        }
        slides = target
        slidesName = source.lastPathComponent
        // Если телефон не смог прочитать PDF, файл всё равно уйдёт на сервер, но без листания.
        document = PDFDocument(url: target)
        pageCount = document?.pageCount ?? 0
        page = 0
        showSlide()
        // Презентацию приложили посреди записи: с этого момента на экране её первый слайд.
        marks = []
        if active { markSlide() }
    }

    func removeSlides() {
        slides = nil
        slidesName = nil
        document = nil
        slideImage = nil
        pageCount = 0
        marks = []
    }

    /// Листает слайды. Во время записи переключение запоминается со временем: по нему сервер считает время на слайд.
    func flip(_ step: Int) {
        let target = min(max(page + step, 0), pageCount - 1)
        guard pageCount > 0, target != page else { return }
        page = target
        showSlide()
        if active { markSlide() }
    }

    private func showSlide() {
        guard let sheet = document?.page(at: page) else {
            slideImage = nil
            return
        }
        let bounds = sheet.bounds(for: .mediaBox)
        let width: CGFloat = 1200
        slideImage = sheet.thumbnail(of: CGSize(width: width, height: width * bounds.height / max(bounds.width, 1)), for: .mediaBox)
    }

    private func markSlide() {
        marks.append(SlideMark(page: page + 1, start: recorder?.elapsed ?? 0))
    }

    func toggle(requestMicrophone: @escaping () async -> Bool) {
        guard let recorder else { return }
        switch recorder.state {
        case .recording:
            recorder.pause()
            sync()
        case .paused:
            recorder.resume()
            startTicker()
            sync()
        case .idle, .stopped:
            Task {
                guard await requestMicrophone() else {
                    hint = L("Без доступа к микрофону запись невозможна. Разрешите доступ в настройках приложения", "Recording is impossible without microphone access. Allow it in the app settings")
                    return
                }
                start()
            }
        }
    }

    private func start() {
        guard let recorder else { return }
        recorder.discard()
        file = nil
        do {
            try recorder.start(to: FileManager.default.temporaryDirectory.appendingPathComponent("speech.wav"))
        } catch {
            recorder.discard()
            sync()
            hint = L("Не удалось включить микрофон", "Could not turn on the microphone")
            return
        }
        // Новая запись: отметки начинаются с того слайда, который сейчас на экране.
        marks = []
        if pageCount > 0 { markSlide() }
        startTicker()
        sync()
    }

    func stop() {
        file = recorder?.stop()
        sync()
    }

    func analyze(app: AppState) {
        guard let recorder else { return }
        if active { file = recorder.stop() }
        guard let file, recorder.elapsed >= Self.minRecording else {
            recorder.discard()
            self.file = nil
            sync()
            hint = L("Запись слишком короткая. Говорите хотя бы три секунды", "The recording is too short. Speak for at least three seconds")
            return
        }
        analyzing = true
        sync()
        Task {
            switch await app.call({ try await $0.uploadSpeech(file: file, slides: self.slides, marks: self.marks) }) {
            case .success(let result):
                handedOver = true
                recorder.discard()
                // Экран записи заменяется результатами: назад с результатов ведёт на главный.
                app.path.removeAll { $0 == .record }
                app.path.append(.results(result))
            case .failure(let failure):
                analyzing = false
                sync()
                if failure.kind != .unauthorized { error = failure }
            }
        }
    }

    /// Экран ушёл с глаз: запись ставим на паузу, чтобы не писать микрофон в фоне.
    func pauseIfRecording() {
        if recorder?.state == .recording {
            recorder?.pause()
            sync()
        }
    }

    func close() {
        ticker?.invalidate()
        if !handedOver { recorder?.discard() }
    }

    private func startTicker() {
        ticker?.invalidate()
        // Таймер показывает миллисекунды и обновляется каждый кадр.
        ticker = Timer.scheduledTimer(withTimeInterval: 0.033, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self, let recorder = self.recorder else { return }
                self.elapsed = recorder.elapsed
                if recorder.state != .recording { self.ticker?.invalidate() }
            }
        }
    }

    private func sync() {
        guard let recorder else { return }
        state = recorder.state
        elapsed = recorder.elapsed
        if analyzing {
            hint = L("Анализируем запись. Это может занять около минуты", "Analyzing the recording. This may take about a minute")
        } else {
            switch state {
            case .recording: hint = L("Идёт запись", "Recording")
            case .paused: hint = L("Запись на паузе", "Recording paused")
            case .stopped: hint = L("Запись готова. Нажмите «Анализ»", "The recording is ready. Tap Analyze")
            case .idle: hint = L("Нажмите на кнопку записи и начните говорить", "Tap the record button and start speaking")
            }
        }
    }
}

struct RecordView: View {
    @EnvironmentObject private var app: AppState
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var model = RecordModel()
    @State private var pickingSlides = false

    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                BackButton().frame(maxWidth: .infinity, alignment: .leading)
                Text(L("ЗАПИСЬ", "RECORDING")).font(.light(34)).italic().foregroundStyle(Color.tmGreyTitle)
                    .padding(.top, 12).padding(.bottom, 44).accessibilityIdentifier("tvTitle")

                VStack(spacing: 34) {
                    Text(Formatters.timer(model.elapsed))
                        .font(.system(size: 30, design: .rounded)).monospacedDigit().foregroundStyle(Color.tmBlue)
                        .accessibilityIdentifier("tvTimer")
                    HStack(spacing: 52) {
                        roundButton(icon: recordIcon, label: recordLabel, id: "btnRecordPause", enabled: !model.analyzing) {
                            model.toggle(requestMicrophone: app.services.requestMicrophone)
                        }
                        roundButton(icon: "stop.fill", label: L("Остановить запись", "Stop recording"), id: "btnStop", enabled: model.active && !model.analyzing) {
                            model.stop()
                        }
                    }
                }
                .padding(.top, 38).padding(.bottom, 34)
                .frame(maxWidth: .infinity)
                .background(RoundedRectangle(cornerRadius: 24).fill(Color.tmPinkCard))
                .overlay(RoundedRectangle(cornerRadius: 24).stroke(Color.tmPinkLine, lineWidth: 1.5))

                // Презентация к выступлению: сервер сравнит слайды с тем, что прозвучало.
                if let name = model.slidesName {
                    HStack(spacing: 8) {
                        Text(L("Презентация: ", "Slides: ") + name).font(.system(size: 16)).foregroundStyle(Color.tmGreyTitle)
                            .lineLimit(1).truncationMode(.middle).accessibilityIdentifier("tvSlidesName")
                        Spacer()
                        Button { model.removeSlides() } label: {
                            Image(systemName: "xmark").foregroundStyle(Color.tmBlueStrong).frame(width: 44, height: 44)
                        }
                        .disabled(model.analyzing)
                        .accessibilityLabel(L("Убрать презентацию", "Remove slides")).accessibilityIdentifier("btnRemoveSlides")
                    }
                    .padding(.leading, 28).padding(.trailing, 16).padding(.top, 28)
                    // Слайды листаются здесь же: каждое переключение во время записи запоминается со временем.
                    if let image = model.slideImage {
                        Image(uiImage: image).resizable().scaledToFit()
                            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.tmPinkLine, lineWidth: 1.5))
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                            .padding(.horizontal, 12).padding(.top, 8)
                            .accessibilityLabel(L("Текущий слайд", "Current slide")).accessibilityIdentifier("ivSlide")
                        HStack(spacing: 12) {
                            Button(L("‹ Назад", "‹ Back")) { model.flip(-1) }.buttonStyle(OutlineButtonStyle()).disabled(model.page == 0)
                                .accessibilityIdentifier("btnPrevSlide")
                            Text(L("Слайд \(model.page + 1) из \(model.pageCount)", "Slide \(model.page + 1) of \(model.pageCount)")).font(.system(size: 15)).foregroundStyle(Color.tmGreyTitle)
                                .fixedSize().accessibilityIdentifier("tvSlideNumber")
                            Button(L("Дальше ›", "Next ›")) { model.flip(1) }.buttonStyle(FilledButtonStyle()).disabled(model.page >= model.pageCount - 1)
                                .accessibilityIdentifier("btnNextSlide")
                        }
                        .padding(.horizontal, 12).padding(.top, 8)
                    }
                } else {
                    Button(L("Прикрепить презентацию (PDF)", "Attach slides (PDF)")) { pickingSlides = true }
                        .buttonStyle(OutlineButtonStyle()).disabled(model.analyzing)
                        .padding(.horizontal, 28).padding(.top, 28)
                        .accessibilityIdentifier("btnAttachSlides")
                }

                Button(L("Анализ", "Analyze")) { model.analyze(app: app) }
                    .buttonStyle(FilledButtonStyle())
                    .disabled(!(model.active || model.state == .stopped) || model.analyzing)
                    .padding(.horizontal, 28).padding(.top, 16)
                    .accessibilityIdentifier("btnAnalyze")

                Text(model.hint).font(.light(17)).foregroundStyle(Color.tmGreyTitle).multilineTextAlignment(.center)
                    .padding(.horizontal, 16).padding(.top, 24).accessibilityIdentifier("tvHint")
                if model.analyzing { ProgressView().tint(.tmBlue).padding(.top, 16) }
            }
            .padding(.horizontal, 20).padding(.top, 8).padding(.bottom, 32)
        }
        .background(Color.white.ignoresSafeArea())
        .onAppear { model.attach(app.services.makeRecorder()) }
        .fileImporter(isPresented: $pickingSlides, allowedContentTypes: [.pdf]) { result in
            if case .success(let url) = result { model.attachSlides(url) }
        }
        .onDisappear { model.close() }
        .onChange(of: scenePhase) { _, phase in if phase != .active { model.pauseIfRecording() } }
        // Экран ошибки закрыли: запись сохранена, анализ можно повторить.
        .errorScreen($model.error, onBack: {}, onRetry: { model.analyze(app: app) })
    }

    private var recordIcon: String {
        switch model.state {
        case .recording: return "pause.fill"
        case .paused: return "play.fill"
        default: return "circle.fill"
        }
    }

    private var recordLabel: String {
        switch model.state {
        case .recording: return L("Пауза", "Pause")
        case .paused: return L("Продолжить запись", "Resume recording")
        default: return L("Начать запись", "Start recording")
        }
    }

    private func roundButton(icon: String, label: String, id: String, enabled: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: icon).font(.system(size: icon == "circle.fill" ? 12 : 18)).foregroundStyle(.white)
                .frame(width: 56, height: 56)
                .background(Circle().fill(enabled ? Color.tmBlue : Color.tmBlueLight))
        }
        .disabled(!enabled)
        .accessibilityLabel(label)
        .accessibilityIdentifier(id)
    }
}

struct ResultsView: View {
    @EnvironmentObject private var app: AppState
    let result: SpeechResult
    @State private var transcriptShown = false

    var body: some View {
        let feedback = result.feedback
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                BackButton().padding(.bottom, 8)
                HStack(spacing: 14) {
                    Text(L("Результаты", "Results")).font(.light(34)).foregroundStyle(Color.tmGreyTitle).accessibilityIdentifier("tvResultsTitle")
                    SVGShape(data: Art.decor, viewBox: CGSize(width: 56, height: 44)).stroke(Color.tmBlueLight, lineWidth: 1.3)
                        .frame(width: 52, height: 40).accessibilityHidden(true)
                }
                Text(L("Рекомендации", "Recommendations")).font(.system(size: 34, weight: .bold)).foregroundStyle(Color.tmBlue)
                    .padding(.bottom, 36).accessibilityIdentifier("tvRecommendationsTitle")

                VStack(spacing: 22) {
                    row(L("Скорость", "Pace"), Formatters.rate(feedback.speechRate), id: "tvRate")
                    row(L("Громкость", "Volume"), Formatters.volume(feedback.volume), id: "tvVolume")
                    row(L("Монотонность", "Intonation"), Formatters.monotonyDescription(feedback.monotony), id: "tvMonotony")
                    row(L("Эмоция речи", "Emotion"), Formatters.emotion(feedback.emotion), id: "tvEmotion")
                    row(L("Чёткость речи", "Clarity"), Formatters.clarity(feedback.clarity, feedback.clarityLevel), id: "tvClarity")
                    row(L("Кол-во\nзаполнителей", "Filler\nwords"), Formatters.fillers(feedback.numFillers), id: "tvFillers")
                    if !feedback.fillers.isEmpty {
                        Text(L("Чаще всего: ", "Most frequent: ") + feedback.fillers.map { L("«\($0)»", "“\($0)”") }.joined(separator: ", "))
                            .font(.light(16)).foregroundStyle(Color.tmGreyTitle)
                            .frame(maxWidth: .infinity, alignment: .leading).padding(.top, -12)
                            .accessibilityIdentifier("tvFillerWords")
                    }
                }
                .padding(.horizontal, 20).padding(.top, 30).padding(.bottom, 22)
                .background(RoundedRectangle(cornerRadius: 28).stroke(Color.tmPinkLine, lineWidth: 1.5))

                // Содержание: о чём выступление и как оно построено. Сервер старой версии этих данных не присылает.
                if let content = result.content {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(L("Основная мысль", "Main idea")).font(.system(size: 18, weight: .bold)).foregroundStyle(Color.tmBlue)
                        Text(content.mainIdea ?? L("Не удалось выделить: в записи слишком мало слов", "Could not find one: the recording has too few words"))
                            .font(.system(size: 18)).foregroundStyle(Color.tmInk).lineSpacing(4)
                            .fixedSize(horizontal: false, vertical: true)
                            .accessibilityIdentifier("tvMainIdea")
                        if let keywords = content.keywords, !keywords.isEmpty {
                            Text(L("Ключевые слова: ", "Key words: ") + keywords.joined(separator: ", "))
                                .font(.light(16)).foregroundStyle(Color.tmGreyTitle).padding(.top, 2)
                                .accessibilityIdentifier("tvKeywords")
                        }
                        HStack {
                            Text(L("Структура", "Structure")).font(.system(size: 18, weight: .bold)).foregroundStyle(Color.tmBlue)
                            Spacer()
                            Text(Formatters.structure(content.structure?.level)).font(.light(19)).foregroundStyle(Color.tmBlue)
                                .accessibilityIdentifier("tvStructure")
                        }
                        .padding(.top, 14)
                        Text(content.structure?.summary ?? "")
                            .font(.light(16)).foregroundStyle(Color.tmGreyTitle).lineSpacing(4)
                            .fixedSize(horizontal: false, vertical: true)
                            .accessibilityIdentifier("tvStructureSummary")
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 20).padding(.top, 24).padding(.bottom, 22)
                    .background(RoundedRectangle(cornerRadius: 28).stroke(Color.tmPinkLine, lineWidth: 1.5))
                    .padding(.top, 18)
                }

                // Презентация: насколько слова совпали со слайдами. Блок есть, только если к записи приложили PDF.
                if let report = result.slides {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(L("Презентация и речь", "Slides and speech")).font(.system(size: 18, weight: .bold)).foregroundStyle(Color.tmBlue)
                        if let error = report.error {
                            Text(error).font(.system(size: 17)).foregroundStyle(Color.tmInk).fixedSize(horizontal: false, vertical: true)
                        } else {
                            Text(Formatters.slidesSummary(report)).font(.system(size: 17)).foregroundStyle(Color.tmInk).lineSpacing(4)
                                .fixedSize(horizontal: false, vertical: true).accessibilityIdentifier("tvSlidesSummary")
                            ForEach(report.notes ?? [], id: \.self) { note in
                                MarkupText(source: note).font(.light(16)).foregroundStyle(Color.tmGreyTitle).lineSpacing(4)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                            ForEach(report.items ?? [], id: \.page) { item in
                                VStack(alignment: .leading, spacing: 2) {
                                    MarkupText(source: L("**Слайд \(item.page).**", "**Slide \(item.page).**") + " " + (item.title ?? ""))
                                    Text(Formatters.slideLine(item))
                                    if let missed = item.missed, !missed.isEmpty {
                                        Text(L("Не прозвучало: ", "Not said: ") + missed.joined(separator: ", "))
                                    }
                                }
                                .font(.system(size: 15)).foregroundStyle(Color.tmGreyTitle)
                                .fixedSize(horizontal: false, vertical: true)
                                .padding(.top, 4)
                            }
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 20).padding(.top, 24).padding(.bottom, 22)
                    .background(RoundedRectangle(cornerRadius: 28).stroke(Color.tmPinkLine, lineWidth: 1.5))
                    .padding(.top, 18)
                    .accessibilityIdentifier("cardSlides")
                }

                if let recommendation = result.recommendation {
                    Text(recommendation.title).font(.system(size: 20, weight: .bold)).foregroundStyle(Color.tmBlue)
                        .padding(.horizontal, 10).padding(.top, 34).accessibilityIdentifier("tvRecTitle")
                    MarkupText(source: recommendation.description)
                        .font(.light(19)).foregroundStyle(Color.tmGreyText).lineSpacing(5)
                        .padding(.horizontal, 10).padding(.top, 4).accessibilityIdentifier("tvRecText")
                }

                // Расшифровка: текст, который сервер распознал в записи. По нему видно, откуда взялись темп и заполнители.
                if !result.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    Button(transcriptShown ? L("Скрыть расшифровку", "Hide transcript") : L("Показать расшифровку", "Show transcript")) { transcriptShown.toggle() }
                        .buttonStyle(OutlineButtonStyle()).padding(.horizontal, 28).padding(.top, 32)
                        .accessibilityIdentifier("btnTranscript")
                    if transcriptShown {
                        if !result.segments.isEmpty {
                            Text(L("Розовым выделены слова-заполнители, подчёркнуты слова, которые прозвучали неразборчиво. Над фразой подписано, если темп вне нормы, речь невнятная или в голосе слышна эмоция.\n",
                                   "Filler words are highlighted in pink, words that were hard to make out are underlined. A note above a phrase tells you when the pace is off, the speech is unclear or the voice carries an emotion.\n")
                                 + TranscriptMarks.summary(result.segments))
                                .font(.light(15)).foregroundStyle(Color.tmGreyTitle).lineSpacing(3)
                                .padding(.horizontal, 10).padding(.top, 16)
                                .accessibilityIdentifier("tvTranscriptLegend")
                        }
                        transcript
                            .font(.light(18)).foregroundStyle(Color.tmGreyTitle).lineSpacing(6)
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.horizontal, 22).padding(.vertical, 24)
                            .background(RoundedRectangle(cornerRadius: 28).stroke(Color.tmPinkLine, lineWidth: 1.5))
                            .padding(.top, 16)
                            .accessibilityIdentifier("tvTranscript")
                    }
                }

                Button(L("Записать заново", "Record again")) {
                    app.path.removeAll { if case .results = $0 { return true } else { return false } }
                    app.path.append(.record)
                }
                .buttonStyle(OutlineButtonStyle()).padding(.horizontal, 28).padding(.top, 16)
                .accessibilityIdentifier("btnAgain")
            }
            .padding(.horizontal, 22).padding(.top, 8).padding(.bottom, 40)
        }
        .background(Color.white.ignoresSafeArea())
    }

    /// Расшифровка с разметкой: над фразой пометки о темпе и окраске, заполнители выделены цветом.
    private var transcript: Text {
        guard !result.segments.isEmpty else { return Text(result.text) }   // сервер старой версии: текст как есть
        var output = AttributedString()
        for (number, segment) in result.segments.enumerated() {
            if number > 0 { output += AttributedString("\n\n") }
            let marks = TranscriptMarks.marks(segment)
            for (index, mark) in marks.enumerated() {
                var piece = AttributedString((index == 0 ? "" : "  ·  ") + mark.text)
                piece.font = .system(size: 15, weight: .bold)
                switch mark.kind {
                case .tempo: piece.foregroundColor = .tmBlueDark
                case .negativeEmotion: piece.foregroundColor = .tmError
                case .emotion: piece.foregroundColor = .tmGreyText
                }
                output += piece
            }
            if !marks.isEmpty { output += AttributedString("\n") }
            for part in segment.parts {
                var piece = AttributedString(part.text)
                if part.filler {
                    piece.foregroundColor = .tmError
                    piece.backgroundColor = .tmPinkCard
                    piece.font = .system(size: 18, weight: .bold)
                } else if part.unclear {
                    // Неразборчивое слово: подчёркнуто и набрано курсивом.
                    piece.underlineStyle = .single
                    piece.font = .system(size: 18, weight: .light).italic()
                }
                output += piece
            }
        }
        return Text(output)
    }

    private func row(_ label: String, _ value: String, id: String, spoken: String? = nil) -> some View {
        HStack(alignment: .center) {
            Text(label).font(.light(19)).foregroundStyle(Color.tmGreyTitle)
            Spacer()
            Text(value).font(.light(19)).foregroundStyle(Color.tmBlue)
                .accessibilityIdentifier(id)
                .accessibilityLabel(spoken ?? value)
        }
    }
}
