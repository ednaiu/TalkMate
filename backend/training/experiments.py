"""Сравнение вариантов модели эмоций на одних и тех же данных. Результаты пишутся в JSON.

    python -m training.experiments --features data/features --out data/experiments.json
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

from speech_analysis.emotion_head import EMOTIONS, softmax

from .evaluate import clip_predictions, report
from .train_head import load_set, predict, split_by_clip, train_head

DUSHA_CLASSES = [EMOTIONS.index(name) for name in ("anger", "happiness", "neutral", "sadness")]

VARIANTS = {
    # имя: (обучающие наборы, слои, признак слоя, размер скрытого слоя)
    "linear_last_mean_dusha": (("dusha",), "last", "mean", 0),
    "linear_last_mean_joint": (("dusha", "resd"), "last", "mean", 0),
    "mlp_all_mean_joint": (("dusha", "resd"), "all", "mean", 256),
    "mlp_all_meanstd_dusha": (("dusha",), "all", "meanstd", 256),
    "mlp_all_meanstd_joint": (("dusha", "resd"), "all", "meanstd", 256),
}


def base_report(data, restrict=None):
    logits = data["base_logits"].astype(np.float64)
    if restrict is not None:
        masked = np.full_like(logits, -1e9)
        masked[:, restrict] = logits[:, restrict]
        logits = masked
    return report(*clip_predictions(softmax(logits), data["clips"], data["y"]), EMOTIONS)


def head_report(head, data, device):
    return report(*clip_predictions(predict(head, data["x"], device), data["clips"], data["y"]), EMOTIONS)


def run(features, seeds=(0, 1, 2), epochs=40, log=print):
    features = Path(features)
    tests = {"dusha": load_set(str(features / "dusha_test_raw.npz")), "resd": load_set(str(features / "resd_test_raw.npz"))}
    results = {"baseline": {
        "dusha_test": base_report(tests["dusha"]),
        "dusha_test_restricted_to_4": base_report(tests["dusha"], DUSHA_CLASSES),
        "resd_test": base_report(tests["resd"]),
    }}

    # Влияет ли подготовка звука на исходную модель.
    results["preprocess"] = {}
    for mode in ("raw", "norm", "denoise"):
        entry = {}
        for name in ("dusha", "resd"):
            path = features / f"{name}_test_{mode}.npz"
            if path.exists():
                entry[name] = {k: base_report(load_set(str(path)))[k] for k in ("accuracy", "macro_f1", "uar", "neutral_false_alarm")}
        results["preprocess"][mode] = entry

    dusha = load_set(str(features / "dusha_train_raw_*.npz"))
    resd = load_set(str(features / "resd_train_raw.npz"))
    results["data"] = {
        "dusha_train_clips": int(len(np.unique(dusha["clips"]))),
        "resd_train_clips": int(len(np.unique(resd["clips"]))),
        "dusha_train_classes": {EMOTIONS[i]: int(n) for i, n in enumerate(np.bincount(dusha["y"], minlength=7)) if n},
    }

    # Разбиение на обучение и проверку одно на все запуски; зерно меняет только инициализацию и порядок батчей.
    # Исходные массивы после разбиения удаляются: вместе с копиями они не помещаются в память.
    train, val = {}, {}
    train["dusha"], val["dusha"] = split_by_clip(dusha, 0.1, 0)
    train["resd"], val["resd"] = split_by_clip(resd, 0.15, 0)
    del dusha, resd

    results["variants"] = {}
    for name, (sets, layers, pooling, hidden) in VARIANTS.items():
        runs = []
        for seed in seeds:
            started = time.time()
            log(f"{name}, seed {seed}")
            head, config, history = train_head({k: train[k] for k in sets}, val, layers=layers, pooling=pooling, hidden=hidden,
                                               epochs=epochs, seed=seed, log=log)
            device = next(head.parameters()).device
            best = max(history, key=lambda h: h["mean"])
            runs.append({
                "seed": seed, "best_epoch": best["epoch"], "val": {k: best[k] for k in ("dusha", "resd")},
                "dusha_test": head_report(head, tests["dusha"], device),
                "resd_test": head_report(head, tests["resd"], device),
                "layer_weights": [round(float(w), 4) for w in head.layer_weights().detach().cpu()],
                "seconds": round(time.time() - started, 1),
            })
        results["variants"][name] = {
            "runs": runs,
            "summary": {
                split: {metric: [round(float(np.mean([r[split][metric] for r in runs])), 4),
                                 round(float(np.std([r[split][metric] for r in runs])), 4)]
                        for metric in ("accuracy", "macro_f1", "uar", "neutral_false_alarm")}
                for split in ("dusha_test", "resd_test")
            },
        }
        log(f"  итог {name}: " + json.dumps(results["variants"][name]["summary"]))
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--features", default="data/features")
    parser.add_argument("--out", default="data/experiments.json")
    parser.add_argument("--epochs", type=int, default=40)
    args = parser.parse_args(argv)
    results = run(args.features, epochs=args.epochs)
    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print("результаты в", args.out)


if __name__ == "__main__":
    main()
