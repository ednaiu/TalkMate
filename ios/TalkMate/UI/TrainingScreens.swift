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
                    HStack(alignment: .top, spacing: 24) {
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
                        Text(L("Презентация: ", "Slides: ") + name).font(.interface(16)).foregroundStyle(Color.tmGreyTitle)
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
                            Text(L("Слайд \(model.page + 1) из \(model.pageCount)", "Slide \(model.page + 1) of \(model.pageCount)")).font(.interface(15)).foregroundStyle(Color.tmGreyTitle)
                                .fixedSize().accessibilityIdentifier("tvSlideNumber")
                            Button(L("Дальше ›", "Next ›")) { model.flip(1) }.buttonStyle(FilledButtonStyle()).disabled(model.page >= model.pageCount - 1)
                                .accessibilityIdentifier("btnNextSlide")
                        }
                        .padding(.horizontal, 12).padding(.top, 8)
                    }
                } else {
                    VStack(spacing: 8) {
                        Button { pickingSlides = true } label: {
                            Label(L("Добавить презентацию", "Add presentation"), systemImage: "paperclip")
                                .font(.interface(17, weight: .semibold))
                                .foregroundStyle(Color.tmBlueStrong)
                                .frame(maxWidth: .infinity, minHeight: 52)
                                .background(Capsule().fill(Color(hex: 0xF2F4FF)))
                                .overlay(Capsule().stroke(Color.tmBlueStrong, lineWidth: 1.5))
                        }
                        .disabled(model.analyzing).opacity(model.analyzing ? 0.45 : 1)
                        .accessibilityIdentifier("btnAttachSlides")
                        Text(L("Необязательно · PDF для разбора речи по слайдам", "Optional · PDF for slide-by-slide speech feedback"))
                            .font(.interface(13)).foregroundStyle(Color.tmGreyTitle)
                            .multilineTextAlignment(.center)
                    }
                    .padding(.horizontal, 28).padding(.top, 28)
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
        .onAppear {
            model.attach(app.services.makeRecorder())
            #if DEBUG
            if ProcessInfo.processInfo.arguments.contains("-uiTesting"),
               ProcessInfo.processInfo.environment["FAKE_SLIDES"] == "1", model.slidesName == nil,
               let url = ScreenshotFixtures.presentation() {
                model.attachSlides(url)
            }
            #endif
        }
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
        let primary = id == "btnRecordPause"
        return VStack(spacing: 10) {
            Button(action: action) {
                Image(systemName: icon)
                    .font(.system(size: icon == "circle.fill" ? 20 : 22, weight: .semibold))
                    .foregroundStyle(.white)
                    .frame(width: 64, height: 64)
                    .background(Circle().fill(enabled ? (primary ? Color.tmBlueStrong : Color.tmBlue) : Color.tmBlueLight))
                    .overlay(Circle().stroke(Color.white.opacity(primary && enabled ? 0.7 : 0), lineWidth: 3).padding(5))
            }
            .disabled(!enabled)
            .accessibilityLabel(label)
            .accessibilityIdentifier(id)
            Text(primary ? label : L("Стоп", "Stop"))
                .font(.system(size: 14, weight: primary ? .semibold : .regular))
                .foregroundStyle(enabled ? Color.tmBlueStrong : Color.tmGreyTitle)
                .multilineTextAlignment(.center)
                .accessibilityHidden(true)
        }
        .frame(maxWidth: .infinity)
    }

}

struct ResultsView: View {
    @EnvironmentObject private var app: AppState
    let result: SpeechResult
    @State private var transcriptShown = false
    @State private var metricsShown = false
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    var body: some View {
        let feedback = result.feedback
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                BackButton().padding(.bottom, 8)
                Text(L("Разбор репетиции", "Rehearsal review"))
                    .font(.title.bold()).foregroundStyle(Color.tmInk)
                    .accessibilityIdentifier("tvResultsTitle")
                if result.duration > 0, result.duration.isFinite {
                    Label(Formatters.slideTime(Int(min(result.duration, 86400))), systemImage: "clock")
                        .font(.callout).foregroundStyle(Color.tmGreyTitle).padding(.top, 8)
                        .accessibilityLabel(L("Длительность записи ", "Recording duration ") + Formatters.slideTime(Int(min(result.duration, 86400))))
                }

                VStack(alignment: .leading, spacing: 12) {
                    Text(L("Коротко о записи", "Your recording at a glance")).font(.headline)
                    Text(observation).font(.body).fixedSize(horizontal: false, vertical: true)
                        .accessibilityIdentifier("resultObservation")
                    Text(L("Автоматический разбор может ошибаться.",
                           "Automated feedback may be inaccurate."))
                        .font(.callout).foregroundStyle(Color.tmGreyTitle)
                }
                .padding(20).frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: 24).fill(Color.tmPink.opacity(0.6)))
                .padding(.top, 24)

                VStack(alignment: .leading, spacing: 12) {
                    Text(L("Что попробовать", "Try next")).font(.headline)
                        .accessibilityIdentifier("tvRecommendationsTitle")
                    Text(nextStep).font(.body).lineSpacing(3).fixedSize(horizontal: false, vertical: true)
                        .accessibilityIdentifier("tvRecText")
                    Button(L("Повторить репетицию", "Rehearse again")) { repeatRecording() }
                        .buttonStyle(StrongButtonStyle())
                        .accessibilityIdentifier("btnAgain")
                }
                .padding(20).frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: 24).fill(Color.tmCard))
                .padding(.top, 16)

                if let strength = strength {
                    VStack(alignment: .leading, spacing: 8) {
                        Label(L("Что уже получается", "What’s working"), systemImage: "checkmark.circle")
                            .font(.headline)
                        Text(strength).font(.body).fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(20).frame(maxWidth: .infinity, alignment: .leading)
                    .background(RoundedRectangle(cornerRadius: 24).stroke(Color.tmPinkLine, lineWidth: 1))
                    .padding(.top, 16)
                }

                VStack(alignment: .leading, spacing: 20) {
                    Text(L("Показатели записи", "Recording details")).font(.headline)
                    row(L("Темп речи", "Speaking pace"), Formatters.rate(feedback.speechRate), id: "tvRate")
                    Text(L("Среднее число распознанных слов за минуту. Подходящий темп зависит от темы и аудитории.",
                           "Average recognised words per minute. A suitable pace depends on your topic and audience."))
                        .font(.callout).foregroundStyle(Color.tmGreyTitle)
                    row(L("Слова-паразиты", "Filler words"), Formatters.fillers(feedback.numFillers), id: "tvFillers")
                    if !feedback.fillers.isEmpty {
                        Text(L("Чаще всего: ", "Most frequent: ") + feedback.fillers.map { L("«\($0)»", "“\($0)”") }.joined(separator: ", "))
                            .font(.callout).foregroundStyle(Color.tmGreyTitle)
                            .accessibilityIdentifier("tvFillerWords")
                    }
                    Button {
                        metricsShown.toggle()
                    } label: {
                        HStack {
                            Text(metricsShown ? L("Скрыть подробности", "Hide details") : L("Все показатели", "All metrics"))
                            Spacer()
                            Image(systemName: metricsShown ? "chevron.up" : "chevron.down")
                        }.font(.body.weight(.medium)).foregroundStyle(Color.tmResultText).frame(minHeight: 44)
                    }
                    .accessibilityIdentifier("btnAllMetrics")
                    .accessibilityValue(metricsShown ? L("Развёрнуто", "Expanded") : L("Свёрнуто", "Collapsed"))
                    if metricsShown {
                        Divider()
                        row(L("Громкость", "Volume"), Formatters.volume(feedback.volume), id: "tvVolume")
                        row(L("Интонация", "Intonation"), intonation, id: "tvMonotony")
                        row(L("Разборчивость", "Intelligibility"), clarityLabel, id: "tvClarity")
                        Text(L("Разборчивость — приблизительная оценка модели по качеству распознавания. Шум, микрофон и язык влияют на результат; это не доля правильно произнесённых слов.",
                               "Intelligibility is an approximate model estimate based on recognition quality. Noise, microphone and language affect it; it is not the proportion of words pronounced correctly."))
                            .font(.callout).foregroundStyle(Color.tmGreyTitle)
                        Text(L("Громкость и интонация зависят от записи и контекста. Они не определяют, насколько убедительно ты выступаешь. Эмоциональные метки в расшифровке — предположения модели, не критерий успеха.",
                               "Volume and intonation depend on the recording and context. They do not determine how convincing you are. Emotional labels in the transcript are model inferences, not a measure of success."))
                            .font(.callout).foregroundStyle(Color.tmGreyTitle)
                    }
                }
                .padding(20).frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: 24).stroke(Color.tmPinkLine, lineWidth: 1))
                .padding(.top, 24)

                // Содержание: о чём выступление и как оно построено. Сервер старой версии этих данных не присылает.
                if let content = result.content {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(L("Основная мысль", "Main idea")).font(.interface(18, weight: .bold)).foregroundStyle(Color.tmInk)
                        Text(content.mainIdea ?? L("Не удалось выделить: в записи слишком мало слов", "Could not find one: the recording has too few words"))
                            .font(.interface(18)).foregroundStyle(Color.tmInk).lineSpacing(4)
                            .fixedSize(horizontal: false, vertical: true)
                            .accessibilityIdentifier("tvMainIdea")
                        if let keywords = content.keywords, !keywords.isEmpty {
                            Text(L("Ключевые слова: ", "Key words: ") + keywords.joined(separator: ", "))
                                .font(.light(16)).foregroundStyle(Color.tmGreyTitle).padding(.top, 2)
                                .accessibilityIdentifier("tvKeywords")
                        }
                        row(L("Структура", "Structure"), Formatters.structure(content.structure?.level), id: "tvStructure")
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
                        Text(L("Презентация и речь", "Slides and speech")).font(.interface(18, weight: .bold)).foregroundStyle(Color.tmInk)
                        if let error = report.error {
                            Text(error).font(.interface(17)).foregroundStyle(Color.tmInk).fixedSize(horizontal: false, vertical: true)
                        } else {
                            Text(Formatters.slidesSummary(report)).font(.interface(17)).foregroundStyle(Color.tmInk).lineSpacing(4)
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
                                .font(.interface(15)).foregroundStyle(Color.tmGreyTitle)
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

                // Расшифровка: текст, который сервер распознал в записи. По нему видно, откуда взялись темп и заполнители.
                if !result.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    Button(transcriptShown ? L("Скрыть расшифровку", "Hide transcript") : L("Показать расшифровку", "Show transcript")) { transcriptShown.toggle() }
                        .buttonStyle(OutlineButtonStyle()).padding(.horizontal, 28).padding(.top, 32)
                        .accessibilityIdentifier("btnTranscript")
                    if transcriptShown {
                        if !result.segments.isEmpty {
                            Text(L("Розовым выделены слова-заполнители, подчёркнуты слова, которые прозвучали неразборчиво. Над фразой подписано, если темп вне нормы, речь невнятная или модель предположила эмоциональную окраску (она может ошибаться).\n",
                                   "Filler words are highlighted in pink, words that were hard to make out are underlined. A note above a phrase tells you when the pace is off, the speech is unclear or the model inferred an emotional tone (it may be wrong).\n")
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
                    piece.font = .system(size: 18, weight: .regular).italic()
                }
                output += piece
            }
        }
        return Text(output)
    }

    private func repeatRecording() {
        app.path.removeAll { if case .results = $0 { return true } else { return false } }
        app.path.append(.record)
    }

    private var observation: String {
        switch result.feedback.volume {
        case "quiet": return L("В этой записи голос звучит тихо.", "Your voice sounds quiet in this recording.")
        case "loud": return L("В этой записи голос звучит громко. Проверь расстояние до микрофона перед следующей попыткой.", "Your voice sounds loud in this recording. Check your microphone distance before the next attempt.")
        default: return L("Запись разобрана. Выбери один приём для следующей попытки и сравни ощущения.", "Your recording has been reviewed. Choose one technique for your next attempt and notice how it feels.")
        }
    }

    private var nextStep: String {
        switch result.feedback.volume {
        case "quiet": return L("Запиши одну фразу с того же расстояния до микрофона и проверь, хорошо ли слышно каждое слово.", "Record one sentence at the same microphone distance and check whether each word is easy to hear.")
        case "loud": return L("Отодвинь микрофон немного дальше и запиши одну фразу обычным голосом. Прослушай, исчезли ли резкие звуки и искажения.", "Move the microphone a little farther away and record one sentence in your normal voice. Listen for harsh sounds or distortion.")
        default: break
        }
        if result.feedback.numFillers > 0 {
            return L("Повтори короткий фрагмент: когда хочется вставить слово-паразит, попробуй вместо него сделать короткую паузу.", "Repeat a short section: when you feel a filler word coming, try a short pause instead.")
        }
        if result.feedback.monotony == "monotone" {
            return L("Выбери главное слово в одной фразе и слегка выдели его голосом. Запиши фразу и сравни звучание.", "Choose the key word in one sentence and gently emphasise it. Record the sentence and compare how it sounds.")
        }
        return L("Выбери короткий фрагмент выступления и запиши его ещё раз. Прослушай, удобно ли следить за мыслью.", "Choose a short part of your talk and record it again. Listen back and check whether the idea is easy to follow.")
    }

    private var strength: String? {
        if result.feedback.monotony == "expressive" {
            return L("По оценке модели, голос звучит разнообразно.", "The model detected variation in your intonation.")
        }
        if result.feedback.numFillers == 0, !result.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return L("В распознанном тексте не обнаружены слова-паразиты.", "No filler words were detected in the recognised text.")
        }
        return nil
    }

    private var intonation: String {
        switch result.feedback.monotony {
        case "monotone": return L("мало изменений", "little variation")
        case "expressive": return L("разнообразная", "varied")
        default: return L("не определена", "not available")
        }
    }

    private var clarityLabel: String {
        switch result.feedback.clarityLevel {
        case "clear": return L("высокая", "high")
        case "medium": return L("средняя", "moderate")
        case "unclear": return L("сниженная", "reduced")
        default: return L("не определена", "not available")
        }
    }

    private func row(_ label: String, _ value: String, id: String, spoken: String? = nil) -> some View {
        Group {
            if dynamicTypeSize.isAccessibilitySize {
                stackedRow(label, value, id: id, spoken: spoken)
            } else {
                ViewThatFits(in: .horizontal) {
                    HStack(alignment: .firstTextBaseline, spacing: 24) {
                        Text(label).fixedSize()
                        Spacer(minLength: 0)
                        Text(value).fontWeight(.medium).fixedSize().accessibilityIdentifier(id).accessibilityLabel(spoken ?? value)
                    }
                    stackedRow(label, value, id: id, spoken: spoken)
                }
            }
        }
        .font(.body).foregroundStyle(Color.tmInk)
    }

    private func stackedRow(_ label: String, _ value: String, id: String, spoken: String?) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
            Text(value).fontWeight(.medium).accessibilityIdentifier(id).accessibilityLabel(spoken ?? value)
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
}
