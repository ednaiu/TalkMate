import SwiftUI

extension Color {
    init(hex: UInt32) {
        self.init(red: Double((hex >> 16) & 0xFF) / 255, green: Double((hex >> 8) & 0xFF) / 255, blue: Double(hex & 0xFF) / 255)
    }

    static let tmPink = Color(hex: 0xFCE4EC)
    static let tmPinkCard = Color(hex: 0xFCE4EC)
    static let tmPinkLine = Color(hex: 0xF7D3DF)
    static let tmPinkShape = Color(hex: 0xF7D3DF)
    static let tmBlue = Color(hex: 0x8C9EF2)
    static let tmBlueCard = Color(hex: 0x97A8F5)
    static let tmBlueDark = Color(hex: 0x5B6FD6)
    /// Насыщенный синий главного экрана: кнопка начала тренировки и значки.
    static let tmBlueStrong = Color(hex: 0x4664D6)
    static let tmBlueBright = Color(hex: 0x4F7BEA)
    static let tmBlueLight = Color(hex: 0xC9D2FA)
    static let tmPaper = Color(hex: 0xFBFBF8)
    static let tmSubtitle = Color(hex: 0x45454D)
    static let tmFieldFill = Color(hex: 0xF4F4FA)
    static let tmFieldStroke = Color(hex: 0xDADDEA)
    static let tmFieldLabel = Color(hex: 0x3C3F52)
    static let tmFieldHintSoft = Color(hex: 0x8A8FA3)
    static let tmCard = Color(hex: 0xFCFCFF)
    static let tmInk = Color(hex: 0x111111)
    static let tmGreyTitle = Color(hex: 0x5C5C61)
    static let tmGreyText = Color(hex: 0x8E8E93)
    static let tmFieldHint = Color(hex: 0x8F98CC)
    static let tmHello = Color(hex: 0x7C7780)
    static let tmError = Color(hex: 0xD2456F)
    static let tmNose = Color(hex: 0xB5DBA0)
}

extension Font {
    /// Декоративный шрифт заголовков («Mate», «speakspeak», «Stats»).
    static func display(_ size: CGFloat) -> Font { .custom("YesevaOne-Regular", size: size) }
    /// Тонкий шрифт слова «Talk».
    static func thin(_ size: CGFloat) -> Font { .custom("PoiretOne-Regular", size: size) }
    static func light(_ size: CGFloat) -> Font { .system(size: size, weight: .light) }
}

/// Мини-разбор строк путей в формате SVG: команды M, L, C, Q, Z в абсолютных координатах.
/// Нужен, чтобы рисовать те же фигуры, что и в Android-версии, из тех же чисел.
struct SVGShape: Shape {
    let data: String
    let viewBox: CGSize

    func path(in rect: CGRect) -> Path {
        var path = Path()
        let scanner = Scanner(string: data.replacingOccurrences(of: ",", with: " "))
        scanner.charactersToBeSkipped = .whitespaces
        var command: Character = "M"
        func number() -> CGFloat { CGFloat(scanner.scanDouble() ?? 0) }
        func point() -> CGPoint { CGPoint(x: number(), y: number()) }
        while !scanner.isAtEnd {
            if let next = scanner.scanCharacter(), next.isLetter {
                command = Character(next.uppercased())
                if command == "Z" { path.closeSubpath(); continue }
            } else {
                scanner.currentIndex = scanner.string.index(before: scanner.currentIndex)
            }
            switch command {
            case "M": path.move(to: point()); command = "L"
            case "L": path.addLine(to: point())
            case "C": let c1 = point(), c2 = point(); path.addCurve(to: point(), control1: c1, control2: c2)
            case "Q": let c = point(); path.addQuadCurve(to: point(), control: c)
            default: _ = scanner.scanCharacter()
            }
        }
        let scale = CGAffineTransform(scaleX: rect.width / viewBox.width, y: rect.height / viewBox.height)
        return path.applying(scale).offsetBy(dx: rect.minX, dy: rect.minY)
    }
}

enum Art {
    // Иллюстрация с микрофоном на карточке тренировки, поле 160x176. Корпус и решётка рисуются с наклоном.
    static let micBase = "M50,160 C50,150 118,150 118,160 C118,170 50,170 50,160 Z"
    static let micStand = "M84,120 L84,154"
    static let micHolder = "M50,82 C50,132 118,132 118,82"
    static let micBody = "M64,50 C64,22 108,22 108,50 L108,84 C108,112 64,112 64,84 Z"
    static let micGrille = "M68,50 L80,50 M68,62 L80,62 M68,74 L80,74 M92,50 L104,50 M92,62 L104,62 M92,74 L104,74"
    static let micAccents = "M40,24 L54,34 M60,8 L66,24"
    // Значки карточек: книга 48x40, столбики 48x44, стрелка 18x24.
    static let book = "M4,6 C12,4 18,5 24,9 L24,36 C18,32 12,31 4,33 Z M44,6 C36,4 30,5 24,9 L24,36 C30,32 36,31 44,33 Z"
    static let bars = "M4,28 L12,28 L12,40 L4,40 Z M19,18 L28,18 L28,40 L19,40 Z M34,4 L44,4 L44,40 L34,40 Z"
    static let chevron = "M4,2 L14,12 L4,22"
    static let star = "M18,1 C20,12 24,15 38,17 C25,21 22,25 20,39 C17,26 13,23 1,22 C13,18 16,13 18,1 Z"
    static let asterisk = "M17,2 L25,3 L23,14 L33,8 L37,15 L26,20 L36,27 L31,34 L22,26 L21,38 L13,37 L16,25 L5,31 L2,23 L13,19 L4,11 L10,5 L18,13 Z"
    static let flower = "M12,6 C18,2 24,6 24,11 C28,3 40,5 38,15 C46,18 44,30 34,29 C30,38 18,36 18,29 C10,38 -2,32 4,23 C-2,16 4,6 12,6 Z"
    static let squiggle = "M184,-4 C204,36 268,28 282,52 C294,74 264,88 276,112 C288,134 336,136 364,124"
    static let squiggleAccents = "M243,84 L255,89 M251,72 L258,83"
    static let backArrow = "M22,4 L4,20 L22,36 L26,32 L12,20 L26,8 Z"
    static let decor = "M3,3 L11,3 L11,25 C11,36 27,36 27,25 L27,3 L35,3 L35,25 C35,46 3,46 3,25 Z M41,3 L50,3 L50,40 L41,40 Z"
}

/// Иллюстрация первого экрана: микрофон с лицом на розовом пятне и звуковая волна.
struct WelcomeArt: View {
    /// Цвет пятна за микрофоном. На розовом фоне оно чуть темнее, иначе его не видно.
    var blob: Color = .tmPink
    private let box = CGSize(width: 360, height: 240)

    var body: some View {
        Canvas { context, size in
            let s = size.width / box.width
            context.scaleBy(x: s, y: s)
            func shape(_ data: String) -> Path { SVGShape(data: data, viewBox: box).path(in: CGRect(origin: .zero, size: box)) }
            func line(_ width: CGFloat) -> StrokeStyle { StrokeStyle(lineWidth: width, lineCap: .round) }

            context.fill(shape("M40,140 C36,70 110,20 190,6 C250,-4 290,30 300,70 C308,100 330,120 328,160 C326,215 270,232 200,232 C120,232 46,215 40,140 Z"), with: .color(blob))
            context.stroke(shape("M110,118 C108,160 122,190 149,190 C176,190 192,172 197,146 M149,190 L149,218"), with: .color(.tmInk), style: line(7))
            context.fill(shape("M116,221 C116,212 182,212 182,221 C182,230 116,230 116,221 Z"), with: .color(.tmInk))

            var mic = context
            mic.translateBy(x: 162, y: 108)
            mic.rotate(by: .degrees(14))
            mic.translateBy(x: -162, y: -108)
            mic.fill(Path(roundedRect: CGRect(x: 126, y: 40, width: 72, height: 136), cornerRadius: 36), with: .color(.tmBlue))
            mic.fill(Path(ellipseIn: CGRect(x: 132, y: 46, width: 60, height: 60)), with: .color(.white))
            for x in [150.0, 174.0] {
                mic.fill(Path(ellipseIn: CGRect(x: x - 3.2, y: 69, width: 6.4, height: 6.4)), with: .color(.tmInk))
            }
            mic.fill(shape("M157,77 L167,77 L162,86 Z"), with: .color(Color(hex: 0x7CC47A)))
            mic.stroke(shape("M146,120 L174,120 M146,132 L174,132 M146,144 L174,144"), with: .color(.tmBlueDark), style: line(6))

            context.stroke(shape("M110,118 L111,108 M197,146 L199,137"), with: .color(.tmInk), style: line(11))
            context.stroke(shape("M220,131 L220,131.1 M233,119 L233,143 M246,109 L246,153 M260,99 L260,163 M274,111 L274,151 M287,122 L287,140 M301,131 L301,131.1"), with: .color(.tmBlue), style: line(7))
        }
        .aspectRatio(box.width / box.height, contentMode: .fit)
        .accessibilityHidden(true)
    }
}

/// Иллюстрация на карточке тренировки: наклонённый микрофон на чёрной стойке.
struct MicArt: View {
    private let box = CGSize(width: 160, height: 176)

    var body: some View {
        let tilt = UnitPoint(x: 86.0 / 160, y: 68.0 / 176)
        ZStack {
            SVGShape(data: Art.micBase, viewBox: box).fill(Color.tmBlueBright)
            SVGShape(data: Art.micStand, viewBox: box).stroke(Color.tmInk, style: StrokeStyle(lineWidth: 6, lineCap: .round))
            SVGShape(data: Art.micHolder, viewBox: box).stroke(Color.tmInk, style: StrokeStyle(lineWidth: 6, lineCap: .round))
            SVGShape(data: Art.micBody, viewBox: box).fill(Color.tmBlueBright).rotationEffect(.degrees(14), anchor: tilt)
            SVGShape(data: Art.micGrille, viewBox: box).stroke(Color(hex: 0x3D5FC9), style: StrokeStyle(lineWidth: 4, lineCap: .round))
                .rotationEffect(.degrees(14), anchor: tilt)
            SVGShape(data: Art.micAccents, viewBox: box).stroke(Color.tmInk, style: StrokeStyle(lineWidth: 3.5, lineCap: .round))
        }
        .aspectRatio(box.width / box.height, contentMode: .fit)
        .accessibilityHidden(true)
    }
}

/// Значок карточки: контур с бледной заливкой.
struct OutlineIcon: View {
    let data: String
    let box: CGSize

    var body: some View {
        ZStack {
            SVGShape(data: data, viewBox: box).fill(Color(hex: 0xDCE6FD))
            SVGShape(data: data, viewBox: box).stroke(Color.tmBlueBright, style: StrokeStyle(lineWidth: 2.5, lineCap: .round, lineJoin: .round))
        }
        .frame(width: box.width, height: box.height)
        .accessibilityHidden(true)
    }
}

/// Лицо из макета: обычное на главном экране, грустное со слезами на экране ошибки.
struct Face: View {
    var sad = false

    var body: some View {
        Canvas { context, size in
            let s = size.width / 200
            func rect(_ x: CGFloat, _ y: CGFloat, _ w: CGFloat, _ h: CGFloat) -> CGRect { CGRect(x: x * s, y: y * s, width: w * s, height: h * s) }
            context.fill(Path(ellipseIn: rect(0, 0, 200, 200)), with: .color(.white))
            let eyeY: CGFloat = sad ? 74 : 79
            for x in [CGFloat(71), 119] {
                context.fill(Path(ellipseIn: rect(x - 5, eyeY, 10, 13)), with: .color(.tmInk))
            }
            var nose = Path()
            let noseTop: CGFloat = sad ? 112 : 104
            nose.move(to: CGPoint(x: 100 * s, y: noseTop * s))
            nose.addLine(to: CGPoint(x: 110 * s, y: (noseTop + 22) * s))
            nose.addLine(to: CGPoint(x: 90 * s, y: (noseTop + 22) * s))
            nose.closeSubpath()
            context.fill(nose, with: .color(.tmNose))
            guard sad else { return }
            for x in [CGFloat(71), 119] {
                var tear = Path()
                tear.move(to: CGPoint(x: x * s, y: 100 * s))
                tear.addCurve(to: CGPoint(x: x * s, y: 121 * s), control1: CGPoint(x: (x - 6) * s, y: 110 * s), control2: CGPoint(x: (x - 6) * s, y: 121 * s))
                tear.addCurve(to: CGPoint(x: x * s, y: 100 * s), control1: CGPoint(x: (x + 6) * s, y: 121 * s), control2: CGPoint(x: (x + 6) * s, y: 110 * s))
                context.fill(tear, with: .color(.tmBlue))
            }
            var mouth = Path()
            mouth.move(to: CGPoint(x: 88 * s, y: 166 * s))
            mouth.addQuadCurve(to: CGPoint(x: 112 * s, y: 166 * s), control: CGPoint(x: 100 * s, y: 150 * s))
            context.stroke(mouth, with: .color(.tmInk), style: StrokeStyle(lineWidth: 1.5 * s, lineCap: .round))
        }
        .accessibilityHidden(true)
    }
}

// MARK: - Общие элементы

struct BackButton: View {
    @EnvironmentObject private var app: AppState
    var id = "btnBack"
    var action: (() -> Void)?

    var body: some View {
        Button { if let action { action() } else { app.back() } } label: {
            ZStack(alignment: .leading) {
                SVGShape(data: Art.backArrow, viewBox: CGSize(width: 56, height: 40))
                    .stroke(Color.tmBlue, style: StrokeStyle(lineWidth: 1.6, lineJoin: .round))
                Capsule().fill(Color.tmBlue).frame(width: 26, height: 12).offset(x: 27)
            }
            .frame(width: 56, height: 40)
            .padding(.vertical, 6)
            .contentShape(Rectangle())
        }
        .accessibilityLabel(L("Назад", "Back"))
        .accessibilityIdentifier(id)
    }
}

struct FilledButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var enabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 16))
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity, minHeight: 50)
            .background(Capsule().fill(enabled ? Color.tmBlue : Color.tmBlueLight))
            .opacity(configuration.isPressed ? 0.8 : 1)
    }
}

struct OutlineButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 16))
            .foregroundStyle(Color.tmBlue)
            .frame(maxWidth: .infinity, minHeight: 50)
            .background(Capsule().stroke(Color.tmBlueLight, lineWidth: 1.5))
            .contentShape(Capsule())
            .opacity(configuration.isPressed ? 0.6 : 1)
    }
}

struct TMField: View {
    /// Подсказки автозаполнения (сохранённые пароли, код из SMS). В UI-тестах выключены: системные окна мешают вводу.
    static var autofill = true
    /// Скрывать ли вводимый пароль. В UI-тестах выключено: симулятор теряет текст, набранный в защищённое поле.
    static var maskPasswords = true

    let hint: String
    @Binding var text: String
    let id: String
    var secure = false
    var keyboard: UIKeyboardType = .default
    var contentType: UITextContentType?
    var capitalization: TextInputAutocapitalization = .never

    var body: some View {
        Group {
            if secure && Self.maskPasswords {
                SecureField("", text: $text, prompt: prompt)
            } else {
                TextField("", text: $text, prompt: prompt)
                    .keyboardType(keyboard)
                    .textInputAutocapitalization(capitalization)
            }
        }
        .textContentType(Self.autofill ? contentType : nil)
        .autocorrectionDisabled()
        .font(.light(17))
        .foregroundStyle(Color.tmInk)
        .padding(.horizontal, 22)
        .frame(height: 54)
        .background(Capsule().stroke(Color.tmBlueLight, lineWidth: 1.5))
        .accessibilityIdentifier(id)
    }

    private var prompt: Text { Text(hint).foregroundColor(.tmFieldHint) }
}

/// Поле экранов входа и регистрации: подпись сверху, светлая заливка, значок справа.
struct AuthField: View {
    let label: String
    let hint: String
    @Binding var text: String
    let id: String
    var secure = false
    var keyboard: UIKeyboardType = .default
    var contentType: UITextContentType?
    var capitalization: TextInputAutocapitalization = .never
    var icon: String?
    var iconLabel = ""
    var onIcon: (() -> Void)?
    @State private var revealed = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label).font(.system(size: 15, weight: .semibold)).foregroundStyle(Color.tmFieldLabel)
            HStack(spacing: 8) {
                Group {
                    if secure && TMField.maskPasswords && !revealed {
                        SecureField("", text: $text, prompt: prompt)
                    } else {
                        TextField("", text: $text, prompt: prompt)
                            .keyboardType(keyboard)
                            .textInputAutocapitalization(capitalization)
                    }
                }
                .textContentType(TMField.autofill ? contentType : nil)
                .autocorrectionDisabled()
                .font(.system(size: 17))
                .foregroundStyle(Color.tmInk)
                .accessibilityIdentifier(id)
                if secure {
                    Button { revealed.toggle() } label: { Image(systemName: revealed ? "eye" : "eye.slash") }
                        .accessibilityLabel(revealed ? L("Скрыть пароль", "Hide password") : L("Показать пароль", "Show password"))
                } else if let icon {
                    Button { onIcon?() } label: { Image(systemName: icon) }.accessibilityLabel(iconLabel)
                }
            }
            .foregroundStyle(Color.tmFieldLabel)
            .padding(.horizontal, 16)
            .frame(height: 52)
            .background(RoundedRectangle(cornerRadius: 14).fill(Color.tmFieldFill))
            .overlay(RoundedRectangle(cornerRadius: 14).stroke(Color.tmFieldStroke, lineWidth: 1))
        }
        .padding(.top, 16)
    }

    private var prompt: Text { Text(hint).foregroundColor(.tmFieldHintSoft) }
}

/// Главная кнопка экранов входа: насыщенный синий, крупный текст.
struct StrongButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var enabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 18, weight: .semibold))
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity, minHeight: 56)
            .background(Capsule().fill(enabled ? Color.tmBlueStrong : Color.tmBlueLight))
            .opacity(configuration.isPressed ? 0.8 : 1)
    }
}

struct FormError: View {
    let text: String?

    var body: some View {
        if let text {
            Text(text)
                .font(.system(size: 16))
                .foregroundStyle(Color.tmError)
                .multilineTextAlignment(.center)
                .frame(maxWidth: .infinity)
                .accessibilityIdentifier("tvError")
        }
    }
}

/// Белый лист со скруглёнными верхними углами на розовом фоне: экраны входа, регистрации и ошибки.
struct Sheet<Content: View>: View {
    var radius: CGFloat = 56
    @ViewBuilder var content: Content

    var body: some View {
        content
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
            .background(
                UnevenRoundedRectangle(topLeadingRadius: radius, topTrailingRadius: radius)
                    .fill(.white)
                    .ignoresSafeArea(edges: .bottom)
            )
    }
}

struct HelloText: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.system(size: 22, weight: .bold))
            .foregroundStyle(Color.tmHello)
            .lineSpacing(4)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 40)
            .accessibilityIdentifier("tvHello")
    }
}

struct MarkupText: View {
    let source: String

    var body: some View {
        Markup.parse(source).reduce(Text("")) { result, segment in
            result + (segment.bold ? Text(segment.text).fontWeight(.bold).foregroundColor(.tmInk) : Text(segment.text))
        }
    }
}

struct ServerAlert: ViewModifier {
    @EnvironmentObject private var app: AppState
    @Binding var shown: Bool
    @State private var address = ""
    @State private var invalid = false

    func body(content: Content) -> some View {
        content
            .alert(L("Адрес сервера", "Server address"), isPresented: $shown) {
                TextField("http://", text: $address).textInputAutocapitalization(.never).keyboardType(.URL)
                Button(L("Сохранить", "Save")) {
                    if Validation.serverURL(address) == nil { app.services.session.serverURL = address } else { invalid = true }
                }
                Button(L("Отмена", "Cancel"), role: .cancel) {}
            }
            .alert(L("Адрес должен начинаться с http:// или https://", "The address must start with http:// or https://"), isPresented: $invalid) { Button(L("Понятно", "OK")) { shown = true } }
            .onChange(of: shown) { _, now in if now { address = app.services.session.serverURL } }
    }
}

func hideKeyboard() {
    UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
}

extension View {
    func serverAlert(_ shown: Binding<Bool>) -> some View { modifier(ServerAlert(shown: shown)) }
}
