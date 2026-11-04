import SwiftUI

enum LegalDocument: String, Identifiable {
    case terms, privacy
    var id: String { rawValue }
    var title: String { self == .terms ? L("Условия использования", "Terms of use") : L("Конфиденциальность", "Privacy") }
}

/// Локальные проекты документов: отсутствие сети не скрывает информацию от пользователя.
struct LegalDocumentView: View {
    @Environment(\.dismiss) private var dismiss
    let document: LegalDocument
    @State private var language = Lang.english ? "en" : "ru"

    private var paragraphs: [String] {
        guard let url = Bundle.main.url(forResource: "\(document.rawValue)-\(language)", withExtension: "md"),
              let source = try? String(contentsOf: url, encoding: .utf8) else {
            return [L("Документ не удалось открыть. Попробуйте снова.", "The document could not be opened. Please try again.")]
        }
        return source.components(separatedBy: "\n\n").filter { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    Text(L("Проект документа. Данные оператора, размещение сервера и сроки хранения ещё не утверждены. Этот проект не является действующими условиями или согласием.",
                           "Draft document. The operator, hosting and retention periods are not confirmed. This draft is not active terms or consent."))
                        .font(.callout).padding(16)
                        .background(RoundedRectangle(cornerRadius: 16).fill(Color.tmPink))
                        .accessibilityIdentifier("legalDraftNotice")
                    Picker(L("Язык документа", "Document language"), selection: $language) {
                        Text("Русский").tag("ru")
                        Text("Français").tag("fr")
                        Text("English").tag("en")
                    }.pickerStyle(.segmented)
                    ForEach(Array(paragraphs.enumerated()), id: \.offset) { _, paragraph in
                        if paragraph.hasPrefix("# ") {
                            Text(String(paragraph.dropFirst(2))).font(.title2.bold()).accessibilityAddTraits(.isHeader)
                        } else if paragraph.hasPrefix("## ") {
                            Text(String(paragraph.dropFirst(3))).font(.headline).accessibilityAddTraits(.isHeader)
                        } else {
                            Text(.init(paragraph)).font(.body).lineSpacing(4).textSelection(.enabled)
                        }
                    }
                }.padding(20).frame(maxWidth: .infinity, alignment: .leading)
            }
            .background(Color.tmPaper).foregroundStyle(Color.tmInk)
            .navigationTitle(document.title).navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button(L("Готово", "Done")) { dismiss() }.accessibilityIdentifier("closeLegalDocument")
                }
            }
        }
    }
}
