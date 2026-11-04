import SwiftUI

struct HomeView: View {
    @EnvironmentObject private var app: AppState

    var body: some View {
        // Карточка тренировки занимает столько места, сколько нужно содержимому, как в макете. Нижние карточки
        // фиксированной высоты; на низком экране содержимое прокручивается.
        GeometryReader { geo in
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                HStack {
                    BrandWordmark(size: 34)
                    Spacer()
                    Button { app.path = [.profile] } label: { Face().frame(width: 52, height: 52) }
                        .accessibilityLabel(L("Профиль", "Profile")).accessibilityIdentifier("btnProfile")
                }
                .padding(.horizontal, 6)
                .padding(.top, 16)

                Text(L("Привет, \(app.userName)!", "Hello, \(app.userName)!"))
                    .font(.light(26)).foregroundStyle(Color.tmGreyTitle).lineLimit(1)
                    .padding(.horizontal, 8).padding(.top, 22)
                    .accessibilityIdentifier("tvWelcomeMessage")

                trainingCard.padding(.top, 14)
                smallCard(id: "cardArticles", route: .articles, icon: OutlineIcon(data: Art.book, box: CGSize(width: 48, height: 40)),
                          title: L("Статьи", "Articles"), subtitle: L("Советы по публичным выступлениям", "Tips on public speaking")).padding(.top, 18)
                smallCard(id: "cardStats", route: .stats, icon: OutlineIcon(data: Art.bars, box: CGSize(width: 48, height: 44)),
                          title: L("Мой прогресс", "My progress"), subtitle: L("Результаты тренировок", "Practice results")).padding(.top, 14)
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 12)
            .frame(minHeight: geo.size.height, alignment: .top)
        }
        }
        .background(
            ZStack {
                Color.tmPink
                SVGShape(data: Art.squiggle, viewBox: CGSize(width: 360, height: 760)).stroke(Color(hex: 0x4A6FE0), lineWidth: 1.8)
                SVGShape(data: Art.squiggleAccents, viewBox: CGSize(width: 360, height: 760))
                    .stroke(Color.tmBlueBright, style: StrokeStyle(lineWidth: 2.2, lineCap: .round))
            }
            .ignoresSafeArea()
        )
        .safeAreaInset(edge: .bottom, spacing: 0) { BottomBar(selected: .home) }
    }

    /// Большая карточка: заголовок, иллюстрация и кнопка начала тренировки. Нажатие в любом месте ведёт к записи.
    private var trainingCard: some View {
        VStack(spacing: 18) {
            HStack(alignment: .center) {
                VStack(alignment: .leading, spacing: 8) {
                    Text(L("ТРЕНИРОВКА РЕЧИ", "SPEECH PRACTICE")).font(.interface(13)).kerning(1.6).foregroundStyle(Color.tmGreyTitle)
                        .accessibilityIdentifier("tvCaption")
                    Text(L("Говори\nувереннее", "Speak with\nconfidence")).font(.interface(35, weight: .bold)).foregroundStyle(Color.tmInk)
                        .lineSpacing(-4).fixedSize(horizontal: false, vertical: true)
                        .accessibilityIdentifier("tvHomeTitle")
                    Text(L("Запиши выступление и узнай, как улучшить свою речь", "Record a talk and learn how to improve your speech")).font(.light(17)).foregroundStyle(Color.tmGreyTitle)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: 0)
                MicArt().frame(width: 150, height: 165).padding(.horizontal, -14)
            }
            .padding(.leading, 8)
            Button { app.path.append(.record) } label: {
                Text(L("Начать тренировку  →", "Start practice  →")).font(.interface(18, weight: .bold)).foregroundStyle(.white)
                    .frame(maxWidth: .infinity, minHeight: 58)
                    .background(Capsule().fill(Color.tmBlueStrong))
            }
            .accessibilityIdentifier("btnStartTraining")
        }
        .padding(.horizontal, 16).padding(.top, 20).padding(.bottom, 18)
        .background(RoundedRectangle(cornerRadius: 22).fill(Color.tmCard))
        .contentShape(RoundedRectangle(cornerRadius: 22))
        .onTapGesture { app.path.append(.record) }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("cardTraining")
    }

    private func smallCard<Icon: View>(id: String, route: Route, icon: Icon, title: String, subtitle: String) -> some View {
        Button { app.path.append(route) } label: {
            HStack(spacing: 24) {
                icon
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(.interface(21, weight: .bold)).foregroundStyle(Color.tmInk)
                    // Подпись переносится на вторую строку, а не обрезается многоточием.
                    Text(subtitle).font(.light(16)).foregroundStyle(Color.tmGreyTitle)
                        .multilineTextAlignment(.leading).fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: 8)
                SVGShape(data: Art.chevron, viewBox: CGSize(width: 18, height: 24))
                    .stroke(Color.tmBlueBright, style: StrokeStyle(lineWidth: 2.5, lineCap: .round, lineJoin: .round))
                    .frame(width: 14, height: 20)
            }
            .padding(.leading, 24).padding(.trailing, 22).padding(.vertical, 20)
            .frame(maxWidth: .infinity, minHeight: 124)
            .background(RoundedRectangle(cornerRadius: 22).fill(Color.tmCard))
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier(id)
    }
}

struct ErrorView: View {
    let message: String
    let onBack: () -> Void
    let onRetry: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            BackButton(id: "btnErrorBack", action: onBack).padding(.leading, 24).padding(.top, 20)
            Face(sad: true).frame(width: 220, height: 220).frame(maxWidth: .infinity).padding(.top, 56)
            Sheet(radius: 48) {
                VStack(alignment: .leading, spacing: 16) {
                    Text("Ooops…").font(.display(46)).foregroundStyle(Color.tmInk).accessibilityIdentifier("tvOoops")
                    Text(message).font(.light(18)).foregroundStyle(Color.tmGreyTitle).lineSpacing(5)
                        .accessibilityIdentifier("tvErrorMessage")
                    Button(L("Попробовать снова", "Try again"), action: onRetry).buttonStyle(FilledButtonStyle()).padding(.top, 8)
                        .accessibilityIdentifier("btnRetry")
                }
                .padding(.horizontal, 24)
                .padding(.top, 44)
            }
            .padding(.horizontal, 22)
            .padding(.top, 14)
        }
        .background(Color.tmPink.ignoresSafeArea())
    }
}

extension View {
    /// Экран «Ooops…» поверх текущего. Назад закрывает и его, и экран под ним; повтор запускает загрузку заново.
    func errorScreen(_ error: Binding<ApiError?>, onBack: @escaping () -> Void, onRetry: @escaping () -> Void) -> some View {
        fullScreenCover(isPresented: Binding(get: { error.wrappedValue != nil }, set: { if !$0 { error.wrappedValue = nil } })) {
            ErrorView(message: error.wrappedValue?.message ?? L("Что-то пошло не так", "Something went wrong"),
                      onBack: { error.wrappedValue = nil; onBack() },
                      onRetry: { error.wrappedValue = nil; onRetry() })
        }
    }
}

struct ArticlesView: View {
    @EnvironmentObject private var app: AppState
    @State private var articles: [ArticleSummary] = []
    @State private var loading = false
    @State private var error: ApiError?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            BackButton().padding(.leading, 16).padding(.top, 8)
            HStack(spacing: 18) {
                SVGShape(data: Art.star, viewBox: CGSize(width: 40, height: 40)).fill(Color.tmPinkShape).frame(width: 36, height: 36)
                SVGShape(data: Art.asterisk, viewBox: CGSize(width: 40, height: 40)).fill(Color.tmPinkShape).frame(width: 36, height: 36)
                SVGShape(data: Art.flower, viewBox: CGSize(width: 44, height: 40)).fill(Color.tmPinkShape).frame(width: 40, height: 36)
                Spacer()
                Text(L("СТАТЬИ", "ARTICLES")).font(.interface(26, weight: .bold)).foregroundStyle(Color.tmInk).accessibilityIdentifier("tvTitle")
            }
            .padding(.horizontal, 22).padding(.top, 4).padding(.bottom, 24)

            ScrollView {
                LazyVStack(spacing: 20) {
                    if loading { ProgressView().tint(.tmBlue).padding(.top, 32) }
                    ForEach(articles) { article in
                        Button { app.path.append(.article(article)) } label: {
                            Text(article.title)
                                .font(.light(26)).italic().foregroundStyle(Color.tmGreyTitle).lineSpacing(6)
                                .multilineTextAlignment(.leading)
                                .frame(maxWidth: .infinity, minHeight: 66, alignment: .topLeading)
                                .padding(.horizontal, 24).padding(.vertical, 26)
                                .background(RoundedRectangle(cornerRadius: 28).stroke(Color.tmPinkLine, lineWidth: 1.5))
                                .contentShape(RoundedRectangle(cornerRadius: 28))
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.horizontal, 20).padding(.bottom, 24).padding(.top, 2)
            }
            .accessibilityIdentifier("rvArticles")
        }
        .background(Color.white.ignoresSafeArea())
        .task { if articles.isEmpty { await load() } }
        .errorScreen($error, onBack: { app.back() }, onRetry: { Task { await load() } })
    }

    private func load() async {
        loading = true
        switch await app.call({ try await $0.articles() }) {
        case .success(let list): articles = list
        case .failure(let failure): if failure.kind != .unauthorized { error = failure }
        }
        loading = false
    }
}

struct ArticleView: View {
    @EnvironmentObject private var app: AppState
    let summary: ArticleSummary
    @State private var content: String?
    @State private var error: ApiError?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                BackButton().padding(.bottom, 8)
                Text(summary.title)
                    .font(.light(26)).italic().foregroundStyle(Color.tmGreyTitle).lineSpacing(6)
                    .padding(.leading, 10).padding(.bottom, 18)
                    .accessibilityIdentifier("tvArticleTitle")
                Group {
                    if let content {
                        MarkupText(source: content)
                            .font(.light(18)).foregroundStyle(Color.tmGreyText).lineSpacing(7)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .accessibilityIdentifier("tvArticleContent")
                    } else {
                        ProgressView().tint(.tmBlue).frame(maxWidth: .infinity, minHeight: 100)
                    }
                }
                .padding(.horizontal, 22).padding(.vertical, 28)
                .background(RoundedRectangle(cornerRadius: 28).stroke(Color.tmPinkLine, lineWidth: 1.5))
            }
            .padding(.horizontal, 20).padding(.top, 8).padding(.bottom, 32)
        }
        .background(Color.white.ignoresSafeArea())
        .task { if content == nil { await load() } }
        .errorScreen($error, onBack: { app.back() }, onRetry: { Task { await load() } })
    }

    private func load() async {
        switch await app.call({ try await $0.article(id: summary.id) }) {
        case .success(let article): content = article.content
        case .failure(let failure): if failure.kind != .unauthorized { error = failure }
        }
    }
}

struct StatsView: View {
    @EnvironmentObject private var app: AppState
    @State private var stats: Stats?
    @State private var error: ApiError?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                VStack(alignment: .leading, spacing: 8) {
                    BackButton()
                    Text("Stats").font(.display(28)).foregroundStyle(Color.tmInk).padding(.leading, 8).accessibilityIdentifier("tvTitle")
                }
                if let stats {
                    if stats.points.isEmpty {
                        Text(L("Здесь появятся графики, когда вы запишете первое выступление в разделе «Тренировка»", "Charts will appear here once you record your first talk in Practice"))
                            .font(.light(17)).foregroundStyle(Color.tmGreyTitle).lineSpacing(5).padding(28)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(RoundedRectangle(cornerRadius: 28).fill(Color.tmPinkCard))
                            .accessibilityIdentifier("tvEmpty")
                    } else {
                        charts(stats)
                    }
                } else {
                    ProgressView().tint(.tmBlue).frame(maxWidth: .infinity).padding(.top, 32)
                }
            }
            .padding(.horizontal, 16).padding(.top, 8).padding(.bottom, 24)
        }
        .background(Color.white.ignoresSafeArea())
        .task { if stats == nil { await load() } }
        .errorScreen($error, onBack: { app.back() }, onRetry: { Task { await load() } })
    }

    @ViewBuilder
    private func charts(_ stats: Stats) -> some View {
        let dates = stats.points.map { Formatters.shortDate($0.date) }
        let t = stats.thresholds
        let num: (String) -> String = { key in t[key].map { Formatters.number($0, decimals: 0) } ?? "?" }
        // Карточки чередуют розовый и синий фон, как в макете.
        LineChart(title: L("Оценка скорости (слов/мин)", "Pace (words per minute)"), values: stats.points.map(\.speechRate), dates: dates,
                  zone: zone(t["rate_slow"], t["rate_fast"]), blue: false, id: "chartRate",
                  note: L("Норма: от \(num("rate_slow")) до \(num("rate_fast")), между пунктирными линиями",
                          "Norm: from \(num("rate_slow")) to \(num("rate_fast")), between the dashed lines"))
        LineChart(title: L("Количество слов-заполнителей", "Number of filler words"), values: stats.points.map { Double($0.numFillers) }, dates: dates,
                  zone: zone(0, t["fillers_max"]), blue: true, id: "chartFillers",
                  note: L("Норма: не больше \(num("fillers_max")), ниже пунктирной линии", "Norm: no more than \(num("fillers_max")), below the dashed line"))
        LineChart(title: L("Громкость, дБ", "Volume, dB"), values: stats.points.map(\.volumeDb), dates: dates,
                  zone: zone(t["volume_quiet_db"], t["volume_loud_db"]), blue: false, decimals: 1, id: "chartVolume",
                  note: L("Норма: от \(num("volume_quiet_db")) до \(num("volume_loud_db")), между пунктирными линиями",
                          "Norm: from \(num("volume_quiet_db")) to \(num("volume_loud_db")), between the dashed lines"))
        LineChart(title: L("Живость интонации", "Liveliness of intonation"), values: stats.points.map(\.pitchVariability), dates: dates,
                  zone: t["monotony_min_semitones"].map { ($0, .infinity) }, blue: true, decimals: 1, id: "chartPitch",
                  note: L("Чем выше, тем выразительнее голос. Ниже пунктирной линии (\(num("monotony_min_semitones"))) речь звучит монотонно",
                          "The higher, the more expressive the voice. Below the dashed line (\(num("monotony_min_semitones"))) the speech sounds monotone"))
        // Чёткость есть только у записей, сделанных после появления этой оценки.
        let withClarity = stats.points.filter { $0.clarity != nil }
        if !withClarity.isEmpty {
            LineChart(title: L("Чёткость речи, %", "Clarity, %"), values: withClarity.compactMap(\.clarity), dates: withClarity.map { Formatters.shortDate($0.date) },
                      zone: t["clarity_unclear"].map { ($0, .infinity) }, blue: false, id: "chartClarity",
                      note: L("Чем выше, тем разборчивее речь. Ниже пунктирной линии (\(num("clarity_unclear"))) она звучит невнятно",
                              "The higher, the clearer the speech. Below the dashed line (\(num("clarity_unclear"))) it sounds unclear"))
        }
    }

    private func zone(_ low: Double?, _ high: Double?) -> (Double, Double)? {
        guard let low, let high else { return nil }
        return (low, high)
    }

    private func load() async {
        switch await app.call({ try await $0.stats() }) {
        case .success(let loaded): stats = loaded
        case .failure(let failure): if failure.kind != .unauthorized { error = failure }
        }
    }
}

/// График показателя по записям: оси со стрелками из макета, линия значений и полоса нормы.
struct LineChart: View {
    let title: String
    let values: [Double]
    let dates: [String]
    let zone: (Double, Double)?
    let blue: Bool
    var decimals = 0
    let id: String
    var note = ""

    var body: some View {
        let textColor: Color = blue ? .white : .tmGreyTitle
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(.interface(17)).foregroundStyle(textColor)
            Text(L("последняя: ", "latest: ") + Formatters.number(values.last ?? 0, decimals: decimals)).font(.interface(14)).foregroundStyle(textColor)
            if !note.isEmpty {
                Text(note).font(.interface(13)).foregroundStyle(textColor.opacity(0.85)).fixedSize(horizontal: false, vertical: true)
            }
            Canvas { context, size in draw(&context, size) }.frame(height: 140).padding(.top, 6)
            HStack {
                Text(dates.first ?? "")
                Spacer()
                if dates.count > 1 { Text(dates.last ?? "") }
            }
            .font(.interface(14)).foregroundStyle(textColor)
        }
        .padding(.horizontal, 26).padding(.vertical, 20)
        .background(RoundedRectangle(cornerRadius: 28).fill(blue ? Color.tmBlueCard : Color.tmPinkCard))
        .accessibilityElement(children: .ignore)
        .accessibilityIdentifier(id)
        .accessibilityLabel("\(title): " + values.map { Formatters.number($0, decimals: decimals) }.joined(separator: ", "))
    }

    private func draw(_ context: inout GraphicsContext, _ size: CGSize) {
        guard !values.isEmpty else { return }
        let left: CGFloat = 4, right = size.width - 4, top: CGFloat = 4, bottom = size.height - 6, arrow: CGFloat = 6
        var low = values.min()!, high = values.max()!
        if let zone {
            low = min(low, zone.0)
            if zone.1.isFinite { high = max(high, zone.1) }
        }
        let pad = max((high - low) * 0.1, 0.5)
        low -= pad
        high += pad
        let plotLeft = left + 8, plotRight = right - 14, plotTop = top + 12
        func y(_ value: Double) -> CGFloat { bottom - CGFloat((value - low) / (high - low)) * (bottom - plotTop) }
        func x(_ index: Int) -> CGFloat {
            values.count == 1 ? (plotLeft + plotRight) / 2 : plotLeft + CGFloat(index) * (plotRight - plotLeft) / CGFloat(values.count - 1)
        }
        // Границы нормы: пунктирные линии. Нулевая граница не рисуется: у счётчика заполнителей норма «от нуля»,
        // и линия у самой оси читалась бы как порог.
        if let zone {
            for bound in [zone.0, zone.1] where bound.isFinite && bound != 0 {
                let line = y(bound)
                guard line > plotTop - 1, line < bottom - 2 else { continue }
                var dash = Path()
                dash.move(to: CGPoint(x: left, y: line))
                dash.addLine(to: CGPoint(x: plotRight, y: line))
                context.stroke(dash, with: .color((blue ? Color.white : Color.tmBlueDark).opacity(0.7)), style: StrokeStyle(lineWidth: 1.2, dash: [6, 5]))
            }
        }
        var axes = Path()
        axes.move(to: CGPoint(x: left, y: top)); axes.addLine(to: CGPoint(x: left, y: bottom)); axes.addLine(to: CGPoint(x: right, y: bottom))
        axes.move(to: CGPoint(x: left - arrow, y: top + arrow)); axes.addLine(to: CGPoint(x: left, y: top)); axes.addLine(to: CGPoint(x: left + arrow, y: top + arrow))
        axes.move(to: CGPoint(x: right - arrow, y: bottom - arrow)); axes.addLine(to: CGPoint(x: right, y: bottom)); axes.addLine(to: CGPoint(x: right - arrow, y: bottom + arrow))
        context.stroke(axes, with: .color(blue ? .tmPink : .tmBlue), style: StrokeStyle(lineWidth: 1.5, lineCap: .round, lineJoin: .round))

        let lineColor: Color = blue ? .white : .tmBlue
        var line = Path()
        for (index, value) in values.enumerated() {
            let point = CGPoint(x: x(index), y: y(value))
            if index == 0 { line.move(to: point) } else { line.addLine(to: point) }
            context.fill(Path(ellipseIn: CGRect(x: point.x - 3.5, y: point.y - 3.5, width: 7, height: 7)), with: .color(lineColor))
        }
        context.stroke(line, with: .color(lineColor), style: StrokeStyle(lineWidth: 2.5, lineCap: .round, lineJoin: .round))
    }
}
