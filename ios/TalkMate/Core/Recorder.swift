import AVFoundation
import Foundation

enum RecorderState { case idle, recording, paused, stopped }

protocol Recorder: AnyObject {
    var state: RecorderState { get }
    /// Сколько звука уже записано, без учёта пауз.
    var elapsed: TimeInterval { get }
    /// Начинает запись в файл. Бросает ошибку, если микрофон недоступен.
    func start(to url: URL) throws
    func pause()
    func resume()
    /// Завершает запись и возвращает готовый файл.
    func stop() -> URL?
    /// Останавливает запись и удаляет файл.
    func discard()
}

struct RecorderError: Error {}

/// Пишет звук с микрофона в WAV 16 кГц моно. Такой файл сервер разбирает без перекодирования.
final class WavRecorder: Recorder {
    static let settings: [String: Any] = [
        AVFormatIDKey: kAudioFormatLinearPCM,
        AVSampleRateKey: 16_000,
        AVNumberOfChannelsKey: 1,
        AVLinearPCMBitDepthKey: 16,
        AVLinearPCMIsFloatKey: false,
        AVLinearPCMIsBigEndianKey: false,
    ]

    private(set) var state: RecorderState = .idle
    private var recorder: AVAudioRecorder?
    private var file: URL?
    private var lastElapsed: TimeInterval = 0

    var elapsed: TimeInterval {
        if let recorder, state == .recording || state == .paused { lastElapsed = recorder.currentTime }
        return lastElapsed
    }

    func start(to url: URL) throws {
        guard state == .idle else { throw RecorderError() }
        let session = AVAudioSession.sharedInstance()
        // Режим .default оставляет системное усиление микрофона. В .measurement оно выключено, и запись
        // получается на 20–25 дБ тише: оценка громкости тогда всегда показывает «тихая».
        try session.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker])
        try session.setActive(true)
        let recorder = try AVAudioRecorder(url: url, settings: Self.settings)
        guard recorder.record() else { throw RecorderError() }
        self.recorder = recorder
        file = url
        lastElapsed = 0
        state = .recording
    }

    func pause() {
        guard state == .recording else { return }
        lastElapsed = recorder?.currentTime ?? lastElapsed
        recorder?.pause()
        state = .paused
    }

    func resume() {
        guard state == .paused else { return }
        recorder?.record()
        state = .recording
    }

    func stop() -> URL? {
        guard state == .recording || state == .paused else { return file }
        lastElapsed = recorder?.currentTime ?? lastElapsed
        recorder?.stop()
        recorder = nil
        state = .stopped
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        return file
    }

    func discard() {
        _ = stop()
        if let file { try? FileManager.default.removeItem(at: file) }
        file = nil
        lastElapsed = 0
        state = .idle
    }

    static func requestPermission() async -> Bool {
        await withCheckedContinuation { continuation in
            AVAudioApplication.requestRecordPermission { continuation.resume(returning: $0) }
        }
    }
}
