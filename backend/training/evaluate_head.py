"""Итоговый замер обученной головы на тестовых выборках в сравнении с исходной моделью.

    python -m training.evaluate_head --head speech_analysis/weights/emotion_head.pt --out data/emotion_report.json
"""
import argparse
import json
from pathlib import Path

import numpy as np

from speech_analysis.emotion_head import EMOTIONS, load_head, softmax

from .evaluate import clip_probabilities, confusion_markdown, decide, report, threshold_curve
from .train_head import load_set, predict


def evaluate_head(head_path, features="data/features"):
    head, meta = load_head(head_path)
    threshold = float(meta.get("negative_threshold", 0.0))
    results = {"negative_threshold": threshold, "val": meta.get("val")}
    for name in ("dusha", "resd"):
        data = load_set(str(Path(features) / f"{name}_test_raw.npz"))
        y_true, base = clip_probabilities(softmax(data["base_logits"].astype(np.float64)), data["clips"], data["y"])
        _, pooled = clip_probabilities(predict(head, data["x"], "cpu"), data["clips"], data["y"])
        results[name] = {
            "baseline": report(y_true, [decide(row) for row in base], EMOTIONS),
            "head": report(y_true, [decide(row) for row in pooled], EMOTIONS),
            "head_with_threshold": report(y_true, [decide(row, threshold) for row in pooled], EMOTIONS),
            "threshold_curve": threshold_curve(y_true, pooled, EMOTIONS),
        }
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--head", default="speech_analysis/weights/emotion_head.pt")
    parser.add_argument("--features", default="data/features")
    parser.add_argument("--out", default="data/emotion_report.json")
    args = parser.parse_args(argv)
    results = evaluate_head(args.head, args.features)
    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    for name in ("dusha", "resd"):
        print(f"\n== {name} ==")
        for variant in ("baseline", "head", "head_with_threshold"):
            r = results[name][variant]
            print(f"{variant:20s} accuracy {r['accuracy']:.4f}  macro-F1 {r['macro_f1']:.4f}  UAR {r['uar']:.4f}  ложные тревоги {r['neutral_false_alarm']:.4f}")
        print(confusion_markdown(results[name]["head_with_threshold"]))


if __name__ == "__main__":
    main()
