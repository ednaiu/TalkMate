"""Подготовка звука перед классификацией эмоций (слайд «Анализ эмоциональной окраски»):
после ресемплинга идут нормализация амплитуды и удаление шума."""
import numpy as np

N_FFT = 512
HOP = 128


def normalize_amplitude(samples, peak=0.95):
    """Приводит пик сигнала к заданному уровню. Тишину не трогает."""
    top = float(np.max(np.abs(samples))) if len(samples) else 0.0
    if top < 1e-6:
        return samples
    return (samples * (peak / top)).astype(np.float32)


def remove_noise(samples, strength=1.5, floor=0.1):
    """Спектральное вычитание: профиль шума оценивается по самым тихим кадрам записи."""
    import librosa

    if len(samples) < N_FFT * 4:
        return samples
    spectrum = librosa.stft(samples, n_fft=N_FFT, hop_length=HOP)
    magnitude = np.abs(spectrum)
    frame_energy = magnitude.sum(axis=0)
    quiet = frame_energy <= np.percentile(frame_energy, 10)
    noise = magnitude[:, quiet].mean(axis=1, keepdims=True)
    gain = np.maximum(1.0 - strength * noise / np.maximum(magnitude, 1e-10), floor)
    cleaned = librosa.istft(spectrum * gain, hop_length=HOP, n_fft=N_FFT, length=len(samples))
    return cleaned.astype(np.float32)


def prepare_for_emotion(samples):
    return normalize_amplitude(remove_noise(normalize_amplitude(samples)))


# Режимы подготовки. Модель должна получать звук в том же виде, в каком его видела при обучении,
# поэтому режим хранится вместе с весами головы.
PREPROCESS_MODES = {
    "raw": lambda samples: samples,
    "norm": normalize_amplitude,
    "denoise": prepare_for_emotion,
}
