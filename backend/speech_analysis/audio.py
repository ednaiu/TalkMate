import numpy as np

SAMPLE_RATE = 16000
MIN_DURATION = 1.0


class AudioError(ValueError):
    """Файл не читается как аудио или запись слишком короткая."""


def load_audio(path):
    """Читает файл, сводит в моно и приводит к 16 кГц."""
    import librosa

    try:
        samples, _ = librosa.load(str(path), sr=SAMPLE_RATE, mono=True)
    except Exception as exc:  # librosa бросает разные типы в зависимости от декодера
        raise AudioError("Не удалось прочитать аудиофайл") from exc
    samples = np.nan_to_num(samples.astype(np.float32))
    if len(samples) < MIN_DURATION * SAMPLE_RATE:
        raise AudioError("Запись слишком короткая: нужна хотя бы одна секунда речи")
    return samples


def duration_seconds(samples):
    return len(samples) / SAMPLE_RATE


def to_pcm16(samples):
    return (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()


def speech_intervals(samples, top_db=35):
    """Интервалы (в отсчётах), где есть звук громче фона."""
    import librosa

    if not np.any(samples):
        return np.empty((0, 2), dtype=int)
    return librosa.effects.split(samples, top_db=top_db, frame_length=1024, hop_length=256)


def dead_air_seconds(samples):
    """Суммарная длительность участков точных нулей длиннее полсекунды.

    Живой микрофон даже в тишине отдаёт слабый шум. Ровные нули означают, что устройство перестало
    передавать звук: так ведёт себя микрофон эмулятора Android, когда теряет связь с компьютером.
    """
    zero = np.concatenate([[0], (samples == 0).astype(np.int8), [0]])
    edges = np.flatnonzero(np.diff(zero))
    runs = edges[1::2] - edges[::2]
    return float(runs[runs >= SAMPLE_RATE // 2].sum()) / SAMPLE_RATE
