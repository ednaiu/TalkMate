import numpy as np

from .audio import speech_intervals

SILENCE_DB = -80.0


def mean_volume_db(samples):
    """Средняя амплитуда (RMS) по участкам с речью, в dBFS."""
    import librosa

    intervals = speech_intervals(samples)
    if len(intervals) == 0:
        return SILENCE_DB
    voiced = np.concatenate([samples[start:end] for start, end in intervals])
    if len(voiced) < 1024:
        return SILENCE_DB
    rms = librosa.feature.rms(y=voiced, frame_length=1024, hop_length=256)[0]
    mean_amplitude = float(np.mean(rms))
    if mean_amplitude <= 1e-8:
        return SILENCE_DB
    return max(SILENCE_DB, 20.0 * float(np.log10(mean_amplitude)))


def classify_volume(volume_db, thresholds):
    if volume_db < thresholds["volume_quiet_db"]:
        return "quiet"
    if volume_db > thresholds["volume_loud_db"]:
        return "loud"
    return "normal"
