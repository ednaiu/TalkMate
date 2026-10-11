"""Дообучение головы эмоций на русской и английской речи сразу.

Голова, обученная только на Dusha и RESD, английскую речь почти не понимает: кодировщик заморожен, но граница
между классами проведена по русским записям. Здесь к ним добавлены английские датасеты, и одна голова учится на
всех. Русские данные остаются в каждом батче, чтобы качество на русском не упало.

    python -m training.train_bilingual --out speech_analysis/weights/emotion_head.pt
"""
import argparse
import json
from pathlib import Path

import numpy as np

from speech_analysis.emotion_head import EMOTIONS, load_head, save_head

from .evaluate import clip_probabilities, decide, pick_threshold, report, threshold_curve
from .train_head import load_set, predict, split_by_clip, train_head

# Доля каждого датасета в батче. Русские наборы вместе держат больше половины.
SHARES = {"dusha": 0.4, "resd": 0.15, "crema": 0.2, "ravdess": 0.05, "meld": 0.2}
TESTS = {"dusha": "ru", "resd": "ru", "crema": "en", "ravdess": "en", "meld": "en"}


def pooled(head, data, device="cpu"):
    return clip_probabilities(predict(head, data["x"], device), data["clips"], data["y"])


def evaluate(head, thresholds, features):
    """Метрики на тестовых частях. thresholds: порог отрицательных эмоций для ru и en."""
    results = {}
    for name, language in TESTS.items():
        data = load_set(str(Path(features) / f"{name}_test_raw.npz"))
        y_true, probabilities = pooled(head, data)
        threshold = thresholds.get(language, 0.0)
        results[name] = {
            "language": language,
            "clips": len(y_true),
            "plain": report(y_true, [decide(row) for row in probabilities], EMOTIONS),
            "with_threshold": report(y_true, [decide(row, threshold) for row in probabilities], EMOTIONS),
        }
        del data
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--features", default="data/features")
    parser.add_argument("--out", default="speech_analysis/weights/emotion_head.pt")
    parser.add_argument("--previous", default="speech_analysis/weights/emotion_head_ru.pt", help="прежняя голова для сравнения")
    parser.add_argument("--results", default="training/results/emotion_english.json")
    parser.add_argument("--shares", default=json.dumps(SHARES), help="доли датасетов в батче; датасет без доли не участвует")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-false-alarm", type=float, default=0.1)
    args = parser.parse_args(argv)
    features = Path(args.features)
    shares = {name: share for name, share in json.loads(args.shares).items() if share > 0}
    total = sum(shares.values())
    shares = {name: share / total for name, share in shares.items()}

    parts, val = {}, {}
    parts["dusha"], val["dusha"] = split_by_clip(load_set(str(features / "dusha_train_raw_*.npz")), 0.1, args.seed)
    parts["resd"], val["resd"] = split_by_clip(load_set(str(features / "resd_train_raw.npz")), 0.15, args.seed)
    val["crema"] = load_set(str(features / "crema_val_raw.npz"))
    val["meld"] = load_set(str(features / "meld_dev_raw.npz"))
    for name in ("crema", "ravdess", "meld"):
        if name in shares:
            parts[name] = load_set(str(features / f"{name}_train_raw.npz"))
    parts = {name: parts[name] for name in shares}
    print("обучение:", {name: len(np.unique(data["clips"])) for name, data in parts.items()}, "доли:", {k: round(v, 2) for k, v in shares.items()})

    head, config, history = train_head(parts, val, epochs=args.epochs, seed=args.seed, shares=shares, select_on=("dusha", "crema", "meld"))
    best = max(history, key=lambda row: row["mean"])
    device = next(head.parameters()).device

    # Пороги подбираются на проверочных частях, тестовые не участвуют. У английской речи порог свой:
    # уверенность модели на ней распределена иначе.
    y_ru, p_ru = pooled(head, val["dusha"], device)
    english = [pooled(head, val[name], device) for name in ("crema", "meld")]
    y_en = [label for labels, _ in english for label in labels]
    p_en = np.concatenate([probabilities for _, probabilities in english])
    thresholds = {
        "ru": pick_threshold(threshold_curve(y_ru, p_ru, EMOTIONS), args.max_false_alarm),
        "en": pick_threshold(threshold_curve(y_en, p_en, EMOTIONS), args.max_false_alarm),
    }
    print("лучшая эпоха:", json.dumps(best, ensure_ascii=False), "пороги:", thresholds)
    del parts, val

    meta = {"labels": EMOTIONS, "val": best, "preprocess": "norm", "negative_threshold": thresholds["ru"],
            "negative_threshold_en": thresholds["en"], "shares": shares}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    save_head(head.cpu(), args.out, config, meta)

    old_head, old_meta = load_head(args.previous)
    old_threshold = float(old_meta.get("negative_threshold", 0.0))
    summary = {
        "shares": shares, "val": best, "thresholds": thresholds,
        "previous": evaluate(old_head, {"ru": old_threshold, "en": old_threshold}, features),
        "bilingual": evaluate(head, thresholds, features),
    }
    Path(args.results).write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{'набор':9s} {'записей':>7s} | прежняя: точность  F1   тревоги | новая: точность  F1   тревоги")
    for name in TESTS:
        old, new = summary["previous"][name]["with_threshold"], summary["bilingual"][name]["with_threshold"]
        print(f"{name:9s} {summary['bilingual'][name]['clips']:7d} |          {old['accuracy']:.3f}  {old['macro_f1']:.3f}  {old['neutral_false_alarm']:.3f}"
              f"  |        {new['accuracy']:.3f}  {new['macro_f1']:.3f}  {new['neutral_false_alarm']:.3f}")


if __name__ == "__main__":
    main()
