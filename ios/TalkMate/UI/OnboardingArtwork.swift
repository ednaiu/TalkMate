import SwiftUI

/// Иллюстрации знакомства. Показатели на карточках — демонстрационные, не результаты пользователя.
struct OnboardingArtwork: View {
    let page: Int
    private let accent = Color(hex: 0x5659DF)

    var body: some View {
        GeometryReader { geometry in
            let scale = max(0, min(geometry.size.width / 340, geometry.size.height / 240))
            ZStack {
                if page == 0 {
                    WelcomeArt(blob: .tmPinkShape).frame(width: 360, height: 240)
                } else {
                    Ellipse().fill(Color.tmPinkShape).frame(width: 292, height: 210)
                    if page == 1 { slides } else { review }
                }
            }
            .frame(width: 340, height: 240)
            .scaleEffect(scale)
            .position(x: geometry.size.width / 2, y: geometry.size.height / 2)
        }
    }

    private var slides: some View {
        ZStack(alignment: .bottomTrailing) {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text(L("Слайд 3 / 12", "Slide 3 / 12")).foregroundStyle(Color.tmSubtitle)
                    Spacer()
                    Circle().fill(Color(hex: 0xED4165)).frame(width: 5, height: 5)
                    Text("01:24").foregroundStyle(Color(hex: 0xED4165))
                }.font(.system(size: 10, weight: .medium))
                Capsule().fill(Color(hex: 0x22232C)).frame(width: 144, height: 10)
                Capsule().fill(Color(hex: 0xDADCE8)).frame(width: 185, height: 7)
                Capsule().fill(Color(hex: 0xDADCE8)).frame(width: 123, height: 7)
                HStack(alignment: .bottom, spacing: 7) {
                    ForEach(Array([18.0, 28, 39, 25].enumerated()), id: \.offset) { index, height in
                        RoundedRectangle(cornerRadius: 4).fill(index == 2 ? accent : Color(hex: 0xB9BAF6))
                            .frame(width: 20, height: height)
                    }
                }.padding(.top, 4)
            }
            .padding(18).frame(width: 248, height: 164)
            .background(RoundedRectangle(cornerRadius: 18).fill(.white))
            .rotationEffect(.degrees(-4))
            Image(systemName: "mic.fill").font(.system(size: 24)).foregroundStyle(.white)
                .frame(width: 62, height: 62).background(Circle().fill(accent))
                .overlay(Circle().stroke(Color.tmPink, lineWidth: 4))
                .offset(x: 18, y: 20)
        }
    }

    private var review: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(L("Разбор репетиции", "Rehearsal review")).font(.system(size: 12, weight: .bold))
                .foregroundStyle(Color.tmInk)
            metric(L("Темп", "Pace"), L("в норме", "on track"), fraction: 0.72, color: accent, positive: true)
            metric(L("Паузы", "Pauses"), L("хорошо", "good"), fraction: 0.58, color: accent, positive: true)
            metric(L("Слова-паразиты", "Filler words"), L("можно лучше", "could improve"), fraction: 0.34, color: Color(hex: 0xE89A21), positive: false)
            HStack(spacing: 7) {
                Image(systemName: "lightbulb")
                Text(L("Замени «ну» на короткую паузу", "Swap “um” for a short pause"))
            }
            .font(.system(size: 9, weight: .medium)).foregroundStyle(Color(hex: 0x343DB0))
            .padding(10).frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: 9).fill(Color(hex: 0xEFF0FF)))
        }
        .padding(16).frame(width: 260)
        .background(RoundedRectangle(cornerRadius: 20).fill(.white))
        .rotationEffect(.degrees(2))
    }

    private func metric(_ title: String, _ value: String, fraction: CGFloat, color: Color, positive: Bool) -> some View {
        VStack(spacing: 4) {
            HStack {
                Text(title).foregroundStyle(Color.tmSubtitle)
                Spacer()
                Text(value).foregroundStyle(positive ? Color(hex: 0x267C49) : Color(hex: 0xA66A19))
            }.font(.system(size: 9, weight: .medium))
            GeometryReader { geometry in
                Capsule().fill(Color(hex: 0xEFF0FF))
                Capsule().fill(color).frame(width: geometry.size.width * fraction)
            }.frame(height: 5)
        }
    }
}
