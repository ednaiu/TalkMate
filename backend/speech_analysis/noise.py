"""Уровень фонового шума: насколько речь громче фона (отношение сигнал/шум, SNR).

Нужен, чтобы не путать плохую дикцию с плохими условиями записи. Если вокруг шумно, модель
распознавания слышит слова хуже, и оценка чёткости падает, хотя человек говорит внятно. Тогда
приложение советует записаться в тишине, а не «говорить чётче».

Метод без отдельной модели: запись режется на кадры по 64 мс, для каждого считается громкость (RMS, dBFS).
Тихие кадры (10-й процентиль) показывают фон, громкие (90-й процентиль) показывают речь. Разница между ними
и есть оценка SNR. В живой речи всегда есть паузы между фразами, поэтому фон в них слышен.
"""
import numpy as np

FRAME = 1024
HOP = 256
# Кадры тише этого уровня считаются цифровой тишиной (нули от устройства) и в оценку фона не входят.
DIGITAL_SILENCE_DB = -90.0
# Если громкость почти не меняется, запись не похожа на речь с паузами, и фон отделить нельзя.
MIN_SPREAD_DB = 3.0
MIN_FRAMES = 20


def frame_levels_db(samples):
    """Громкость каждого кадра в dBFS."""
    if len(samples) < FRAME:
        return np.empty(0)
    count = 1 + (len(samples) - FRAME) // HOP
    index = np.arange(FRAME)[None, :] + HOP * np.arange(count)[:, None]
    rms = np.sqrt(np.mean(np.square(samples[index].astype(np.float64)), axis=1))
    with np.errstate(divide="ignore"):
        return 20.0 * np.log10(np.maximum(rms, 1e-12))


def estimate_snr_db(samples):
    """Оценка SNR в дБ или None, если по записи её не определить."""
    levels = frame_levels_db(samples)
    levels = levels[levels > DIGITAL_SILENCE_DB]
    if len(levels) < MIN_FRAMES:
        return None
    noise, speech = np.percentile(levels, [10, 90])
    spread = float(speech - noise)
    if spread < MIN_SPREAD_DB:
        return None
    return round(min(spread, 60.0), 1)


def classify_noise(snr_db, thresholds):
    """noisy, если речь слишком мало громче фона; clean, если фон не мешает; None, если не определено."""
    if snr_db is None:
        return None
    return "noisy" if snr_db < thresholds["noise_snr_min_db"] else "clean"
