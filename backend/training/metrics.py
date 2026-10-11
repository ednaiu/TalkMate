"""F1-мера со слайда «Обучение модели»: F1 = 2 * Точность * Полнота / (Точность + Полнота)."""


def f1_for_class(y_true, y_pred, label):
    true_positive = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
    predicted = sum(1 for p in y_pred if p == label)
    actual = sum(1 for t in y_true if t == label)
    if true_positive == 0:
        return 0.0
    precision = true_positive / predicted
    recall = true_positive / actual
    return 2 * precision * recall / (precision + recall)


def macro_f1(y_true, y_pred):
    """Среднее F1 по классам, которые есть в разметке."""
    labels = sorted(set(y_true))
    if not labels:
        return 0.0
    return sum(f1_for_class(y_true, y_pred, label) for label in labels) / len(labels)
