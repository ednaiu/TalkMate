"""Оценка качества классификатора эмоций."""
import numpy as np

from speech_analysis.emotion_head import NEGATIVE, decide

from .metrics import f1_for_class, macro_f1


def clip_probabilities(probabilities, clips, labels):
    """Сводит окна к записям: вероятности окон одной записи усредняются. Возвращает (метки, вероятности)."""
    order = np.argsort(clips, kind="stable")
    clips, probabilities, labels = clips[order], probabilities[order], labels[order]
    bounds = np.flatnonzero(np.diff(clips)) + 1
    y_true = [int(chunk[0]) for chunk in np.split(labels, bounds)]
    pooled = np.stack([chunk.mean(axis=0) for chunk in np.split(probabilities, bounds)])
    return y_true, pooled


def clip_predictions(probabilities, clips, labels, negative_threshold=0.0):
    """Предсказание по записи. Порог для отрицательных эмоций описан в speech_analysis.emotion_head.decide."""
    y_true, pooled = clip_probabilities(probabilities, clips, labels)
    return y_true, [decide(row, negative_threshold) for row in pooled]


def threshold_curve(y_true, pooled, names, thresholds=None):
    """Как порог для отрицательных эмоций меняет качество: по строке на каждое значение порога."""
    thresholds = thresholds if thresholds is not None else [0.0] + [round(0.3 + 0.05 * i, 2) for i in range(13)]
    rows = []
    for threshold in thresholds:
        result = report(y_true, [decide(row, threshold) for row in pooled], names)
        rows.append({"threshold": threshold, **{k: result[k] for k in ("accuracy", "macro_f1", "uar", "neutral_false_alarm")}})
    return rows


def pick_threshold(curve, max_false_alarm):
    """Наименьший порог, при котором ложных тревог на нейтральной речи не больше заданной доли."""
    for row in curve:
        if row["neutral_false_alarm"] <= max_false_alarm:
            return row["threshold"]
    return curve[-1]["threshold"]


def report(y_true, y_pred, names):
    """Точность, macro-F1, UAR (средняя полнота по классам), метрики по классам и матрица ошибок."""
    present = sorted(set(y_true))
    per_class, recalls = {}, []
    for label in present:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        actual = sum(1 for t in y_true if t == label)
        predicted = sum(1 for p in y_pred if p == label)
        recall = tp / actual
        recalls.append(recall)
        per_class[names[label]] = {
            "precision": round(tp / predicted, 4) if predicted else 0.0,
            "recall": round(recall, 4),
            "f1": round(f1_for_class(y_true, y_pred, label), 4),
            "support": actual,
        }
    columns = sorted(set(y_true) | set(y_pred))
    confusion = {names[t]: {names[p]: 0 for p in columns} for t in present}
    for t, p in zip(y_true, y_pred):
        confusion[names[t]][names[p]] += 1
    return {
        "n": len(y_true),
        "neutral_false_alarm": false_alarm_rate(y_true, y_pred, names),
        "accuracy": round(float(np.mean(np.array(y_true) == np.array(y_pred))), 4),
        "macro_f1": round(macro_f1(y_true, y_pred), 4),
        "uar": round(float(np.mean(recalls)), 4),
        "per_class": per_class,
        "confusion": confusion,
    }


def false_alarm_rate(y_true, y_pred, names):
    """Доля нейтральных записей, в которых модель услышала отрицательную эмоцию.

    Это прямая цена ошибки для приложения: на отрицательную эмоцию оно выдаёт совет «следить за
    настроением речи», и спокойному докладчику такой совет показывать не за что.
    """
    neutral = names.index("neutral")
    negative = {names.index(name) for name in NEGATIVE}
    predictions = [p for t, p in zip(y_true, y_pred) if t == neutral]
    if not predictions:
        return 0.0
    return round(sum(1 for p in predictions if p in negative) / len(predictions), 4)


def confusion_markdown(result):
    rows = list(result["confusion"])
    columns = list(next(iter(result["confusion"].values())))
    lines = ["| истина \\\\ ответ | " + " | ".join(columns) + " |", "| --- |" + " ---: |" * len(columns)]
    for row in rows:
        lines.append(f"| {row} | " + " | ".join(str(result["confusion"][row][c]) for c in columns) + " |")
    return "\n".join(lines)
