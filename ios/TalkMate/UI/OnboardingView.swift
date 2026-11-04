import SwiftUI

struct WelcomeView: View {
    @EnvironmentObject private var app: AppState
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @ScaledMetric(relativeTo: .title) private var headingSize = 28.0
    @ScaledMetric(relativeTo: .body) private var bodySize = 16.0
    @ScaledMetric(relativeTo: .subheadline) private var tagSize = 14.0
    @State private var page = 0
    @State private var serverShown = false
    @State private var document: LegalDocument?

    private let accent = Color(hex: 0x5659DF)
    private let tagBackground = Color(hex: 0xEFF0FF)

    var body: some View {
        GeometryReader { geometry in
            let artHeight = dynamicTypeSize.isAccessibilitySize ? 150.0 : min(248, max(160, geometry.size.height * 0.32))
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(spacing: 0) {
                        VStack(spacing: 0) {
                            header
                            OnboardingArtwork(page: page)
                                .frame(maxWidth: 360)
                                .frame(height: artHeight)
                                .frame(maxWidth: .infinity)
                                .accessibilityHidden(true)
                        }
                        .padding(.top, 4).padding(.bottom, 12)
                        .id("onboardingTop")

                        introduction
                            .padding(.horizontal, 24).padding(.top, 24).padding(.bottom, 16)
                            .frame(maxWidth: .infinity)
                            .frame(minHeight: max(0, geometry.size.height - artHeight - 60), alignment: .top)
                            .background(
                                UnevenRoundedRectangle(topLeadingRadius: 32, topTrailingRadius: 32)
                                    .fill(.white).ignoresSafeArea(edges: .bottom)
                            )
                    }
                    .frame(minHeight: geometry.size.height, alignment: .top)
                }
                .scrollBounceBehavior(.basedOnSize)
                .simultaneousGesture(DragGesture(minimumDistance: 45).onEnded { value in
                    guard abs(value.translation.width) > abs(value.translation.height) * 1.5 else { return }
                    move(to: page + (value.translation.width < 0 ? 1 : -1))
                })
                .onChange(of: page) { _, _ in proxy.scrollTo("onboardingTop", anchor: .top) }
            }
            .background {
                VStack(spacing: 0) {
                    Color.tmPink
                    Color.white.frame(height: geometry.size.height * 0.25)
                }.ignoresSafeArea()
            }
        }
        .serverAlert($serverShown)
        .sheet(item: $document) { LegalDocumentView(document: $0) }
    }

    private var header: some View {
        HStack(spacing: 8) {
            if page == 0 {
                Image(systemName: "mic.fill").font(.system(size: 17, weight: .medium))
                    .foregroundStyle(.white).frame(width: 28, height: 28)
                    .background(RoundedRectangle(cornerRadius: 9).fill(accent))
                    .accessibilityHidden(true)
                BrandWordmark(size: 18, layout: .inline)
                    .contentShape(Rectangle()).onLongPressGesture { serverShown = true }
            } else {
                Button { move(to: page - 1) } label: {
                    Image(systemName: "chevron.left").font(.system(size: 15, weight: .medium))
                        .foregroundStyle(Color.tmInk).frame(width: 44, height: 44, alignment: .leading)
                }
                .accessibilityLabel(L("Назад", "Back")).accessibilityIdentifier("onboardingBack")
            }
            Spacer()
            if page < 2 {
                Button(L("Пропустить", "Skip")) { register() }
                    .font(.system(size: 15, weight: .medium)).foregroundStyle(Color.tmGreyTitle)
                    .frame(minWidth: 44, minHeight: 44)
                    .accessibilityIdentifier("onboardingSkip")
            }
        }
        .padding(.horizontal, 24).frame(height: 44)
    }

    private var introduction: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 6) {
                ForEach(0..<3) { index in
                    Capsule().fill(index == page ? accent : Color(hex: 0xD9DBEA))
                        .frame(width: index == page ? 22 : 6, height: 6)
                }
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(L("Шаг \(page + 1) из 3", "Step \(page + 1) of 3"))
            .accessibilityIdentifier("onboardingPageIndicator")
            .accessibilityAdjustableAction { direction in
                switch direction {
                case .increment: move(to: page + 1)
                case .decrement: move(to: page - 1)
                @unknown default: break
                }
            }

            Text(title).font(.system(size: headingSize, weight: .bold)).tracking(-0.65)
                .foregroundStyle(Color.tmInk).fixedSize(horizontal: false, vertical: true)
                .padding(.top, 20).accessibilityAddTraits(.isHeader)
                .accessibilityIdentifier("welcomeHeading")
            Text(subtitle).font(.system(size: bodySize)).foregroundStyle(Color.tmSubtitle)
                .lineSpacing(3).fixedSize(horizontal: false, vertical: true).padding(.top, 12)
                .accessibilityIdentifier("tvSubtitle")

            OnboardingTagFlow(spacing: 8) {
                ForEach(tags, id: \.title) { tag in
                    Label(tag.title, systemImage: tag.icon)
                        .font(.system(size: tagSize, weight: .medium))
                        .foregroundStyle(Color(hex: 0x343DB0))
                        .padding(.horizontal, 12).padding(.vertical, 8)
                        .background(Capsule().fill(tagBackground))
                }
            }.padding(.top, 20)

            if let notice = app.notice {
                Text(notice).font(.callout).foregroundStyle(Color.tmGreyTitle)
                    .padding(.top, 16).accessibilityIdentifier("tvNotice")
            }

            Spacer(minLength: 32)
            Button {
                if page < 2 { move(to: page + 1) } else { register() }
            } label: {
                HStack(spacing: 10) {
                    if page == 0 { Image(systemName: "mic.fill").accessibilityHidden(true) }
                    Text(page == 0 ? L("Начать репетицию", "Start rehearsing") : page == 1 ? L("Далее", "Next") : L("Создать аккаунт", "Create account"))
                }
            }
            .buttonStyle(OnboardingActionStyle())
            .accessibilityIdentifier("btnRegistration")

            Group {
                if dynamicTypeSize.isAccessibilitySize { VStack(spacing: 4) { loginPrompt } }
                else {
                    ViewThatFits(in: .horizontal) {
                        HStack(spacing: 4) { loginPrompt }
                        VStack(spacing: 4) { loginPrompt }
                    }
                }
            }
            .frame(maxWidth: .infinity).padding(.top, 4)

            if page != 1 { legalLinks.padding(.top, 4) }
        }
    }

    @ViewBuilder private var loginPrompt: some View {
        Text(L("Уже есть аккаунт?", "Already have an account?"))
            .font(.system(size: tagSize)).foregroundStyle(Color.tmSubtitle)
        Button(L("Войти", "Log in")) { app.notice = nil; app.path.append(.login) }
            .font(.system(size: tagSize, weight: .semibold)).foregroundStyle(Color(hex: 0x434BCD))
            .frame(minWidth: 44, minHeight: 44).accessibilityIdentifier("btnLogin")
    }

    private var legalLinks: some View {
        Text(.init(L("Перед началом ознакомься с [условиями](talkmate://terms) и [политикой конфиденциальности](talkmate://privacy).",
                     "Before you start, read the [Terms](talkmate://terms) and [Privacy Policy](talkmate://privacy).")))
            .font(.system(size: max(12, tagSize - 2))).foregroundStyle(Color.tmGreyTitle)
            .tint(Color.tmGreyTitle).multilineTextAlignment(.center)
            .frame(maxWidth: .infinity)
            .environment(\.openURL, OpenURLAction { url in
                if url.host == "terms" { document = .terms; return .handled }
                if url.host == "privacy" { document = .privacy; return .handled }
                return .systemAction
            })
            .accessibilityIdentifier("onboardingLegalLinks")
    }

    private var title: String {
        switch page {
        case 1: return L("Репетируй так,\nкак будешь выступать", "Rehearse the way\nyou’ll present")
        case 2: return L("Каждая репетиция —\nлучше предыдущей", "Every rehearsal\nbeats the last")
        default: return L("Выступай уверенно\nс первой репетиции", "Speak with confidence\nfrom your first rehearsal")
        }
    }

    private var subtitle: String {
        switch page {
        case 1: return L("Добавь слайды и листай их во время записи — или просто говори без них.", "Add your slides and flip through them while recording — or just speak without them.")
        case 2: return L("После записи получишь разбор и советы, что поправить к следующему разу.", "After each recording you get a review and tips for next time.")
        default: return L("Запиши речь со слайдами или без — Talk Mate разберёт темп, паузы и слова-паразиты.", "Record your talk with or without slides — Talk Mate checks your pace, pauses and filler words.")
        }
    }

    private var tags: [(title: String, icon: String)] {
        switch page {
        case 1: return [(L("Со слайдами", "With slides"), "display"), (L("Без слайдов", "No slides"), "mic"), (L("Таймер", "Timer"), "timer")]
        case 2: return [(L("Разбор", "Review"), "chart.bar.xaxis"), (L("Советы", "Tips"), "lightbulb"), (L("Прогресс", "Progress"), "chart.line.uptrend.xyaxis")]
        default: return [(L("Темп речи", "Pace"), "speedometer"), (L("Паузы", "Pauses"), "pause"), (L("Слова-паразиты", "Filler words"), "text.bubble")]
        }
    }

    private func move(to target: Int) {
        let target = min(2, max(0, target))
        guard target != page else { return }
        withAnimation(reduceMotion ? nil : .easeInOut(duration: 0.2)) { page = target }
    }

    private func register() { app.notice = nil; app.path.append(.signUp) }
}

private struct OnboardingActionStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label.font(.headline).foregroundStyle(.white)
            .multilineTextAlignment(.center).fixedSize(horizontal: false, vertical: true)
            .padding(.horizontal, 18).padding(.vertical, 16)
            .frame(maxWidth: .infinity, minHeight: 56)
            .background(RoundedRectangle(cornerRadius: 17).fill(Color(hex: 0x5659DF)))
            .opacity(configuration.isPressed ? 0.8 : 1)
    }
}

private struct OnboardingTagFlow: Layout {
    let spacing: CGFloat

    private func arrange(_ subviews: Subviews, width: CGFloat) -> (CGSize, [CGPoint], [CGSize]) {
        var positions: [CGPoint] = [], sizes: [CGSize] = []
        var x: CGFloat = 0, y: CGFloat = 0, rowHeight: CGFloat = 0, maxX: CGFloat = 0
        for view in subviews {
            let natural = view.sizeThatFits(.unspecified)
            let size = view.sizeThatFits(ProposedViewSize(width: min(natural.width, width), height: nil))
            if x > 0 && x + size.width > width { x = 0; y += rowHeight + spacing; rowHeight = 0 }
            positions.append(CGPoint(x: x, y: y)); sizes.append(size)
            x += size.width + spacing; maxX = max(maxX, x - spacing); rowHeight = max(rowHeight, size.height)
        }
        return (CGSize(width: maxX, height: y + rowHeight), positions, sizes)
    }

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        arrange(subviews, width: max(1, proposal.width ?? 400)).0
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let (_, points, sizes) = arrange(subviews, width: max(1, bounds.width))
        for index in subviews.indices {
            subviews[index].place(at: CGPoint(x: bounds.minX + points[index].x, y: bounds.minY + points[index].y), proposal: ProposedViewSize(sizes[index]))
        }
    }
}
