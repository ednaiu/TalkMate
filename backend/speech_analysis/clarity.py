"""Чёткость (разборчивость) речи по уверенности модели распознавания.

Модель для каждого кусочка текста сообщает вероятность, с которой она его узнала. Невнятно сказанное
слово она узнаёт неуверенно. На 444 записях трёх корпусов средняя уверенность по записи коррелирует
с долей ошибок распознавания (r = −0,67), поэтому её можно показывать как оценку разборчивости.

Оценка зависит не только от дикции: шум и плохой микрофон тоже её снижают.
"""
import numpy as np

# Перевод средней уверенности в понятную шкалу: примерная доля слов, которую модель распознаёт верно.
# Точки взяты из замера: средняя доля ошибок в записях с такой уверенностью (training/results, docs/MODELS.md).
CALIBRATION = [(0.0, 0.0), (0.70, 8.0), (0.84, 40.0), (0.905, 75.0), (0.95, 86.0), (0.985, 95.0), (1.0, 98.0)]

# Слово считается неразборчивым, если модель не уверена хотя бы в одном его кусочке.
UNCLEAR_WORD_PROBABILITY = 0.5


def clarity_score(probabilities):
    """Чёткость в процентах по вероятностям кусочков текста или None, если модель их не сообщает."""
    values = [p for p in probabilities if p is not None]
    if not values:
        return None
    confidence = float(np.mean(values))
    xs, ys = zip(*CALIBRATION)
    return float(np.interp(confidence, xs, ys))


def classify_clarity(score, thresholds):
    if score is None:
        return None
    if score < thresholds["clarity_unclear"]:
        return "unclear"
    if score < thresholds["clarity_clear"]:
        return "medium"
    return "clear"
