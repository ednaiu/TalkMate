import numpy as np

from .audio import SAMPLE_RATE

SEGMENT_SEC = 0.5
FMIN = 65.0
FMAX = 400.0
FRAME = 1024
HOP = 256


def segment_pitches(samples, segment_sec=SEGMENT_SEC):
    """Делит запись на сегменты и возвращает основную частоту каждого озвученного сегмента, Гц."""
    import librosa

    if len(samples) < FRAME * 2:
        return np.array([])
    f0 = librosa.yin(samples, fmin=FMIN, fmax=FMAX, sr=SAMPLE_RATE, frame_length=FRAME, hop_length=HOP)
    rms = librosa.feature.rms(y=samples, frame_length=FRAME, hop_length=HOP)[0]
    n = min(len(f0), len(rms))
    f0, rms = f0[:n], rms[:n]
    peak = float(rms.max()) if n else 0.0
    if peak <= 1e-6:
        return np.array([])
    # Озвученными считаем кадры заметно громче фона и с частотой внутри речевого диапазона.
    voiced = (rms > peak * 0.1) & (f0 > FMIN * 1.05) & (f0 < FMAX * 0.95)

    frames_per_segment = max(1, int(segment_sec * SAMPLE_RATE / HOP))
    pitches = []
    for start in range(0, n, frames_per_segment):
        mask = voiced[start:start + frames_per_segment]
        if mask.sum() >= max(3, frames_per_segment // 4):
            pitches.append(float(np.median(f0[start:start + frames_per_segment][mask])))
    return np.array(pitches)


def pitch_variability(samples):
    """Метрика изменчивости: стандартное отклонение тона сегментов в полутонах."""
    pitches = segment_pitches(samples)
    if len(pitches) < 2:
        return 0.0
    semitones = 12.0 * np.log2(pitches / np.median(pitches))
    return float(np.std(semitones))


def classify_monotony(variability, thresholds):
    return "monotone" if variability < thresholds["monotony_min_semitones"] else "expressive"
