"""Обучение головы классификатора эмоций на признаках замороженного кодировщика.

Данные: Dusha (живая речь, четыре эмоции) и RESD (актёрская речь, семь эмоций) вместе.
Одна Dusha стёрла бы у модели страх, отвращение и интерес: в ней таких меток нет.

Инструменты те же, что на слайде «Обучение модели»: PyTorch, перекрёстная энтропия, Adam, F1 по эпохам.

    python -m training.train_head --dusha data/features/dusha_train_raw.npz --resd data/features/resd_train_raw.npz \\
        --out speech_analysis/weights/emotion_head.pt
"""
import argparse
import glob
import json
from pathlib import Path

import numpy as np

from speech_analysis.emotion_head import EMOTIONS, build_head, pick_device, save_head

from .evaluate import clip_predictions, clip_probabilities, pick_threshold, report, threshold_curve


def load_set(pattern):
    """Читает один или несколько файлов признаков. Номера записей сдвигаются, чтобы не совпадать между файлами.

    Признаки занимают гигабайты, поэтому массив выделяется один раз и заполняется по файлам.
    """
    paths = sorted(glob.glob(pattern)) if isinstance(pattern, str) else list(pattern)
    if not paths:
        raise FileNotFoundError(f"нет файлов признаков: {pattern}")
    sizes = []
    for path in paths:
        with np.load(path) as data:
            sizes.append(len(data["labels"]))
    features, labels, clips, logits = None, [], [], []
    offset, row = 0, 0
    for path, size in zip(paths, sizes):
        with np.load(path) as data:
            part = data["features"]
            if features is None:
                features = np.empty((sum(sizes),) + part.shape[1:], dtype=np.float16)
            features[row:row + size] = part
            del part
            shifted = data["clips"].astype(np.int64) + offset
            offset = int(shifted.max()) + 1
            clips.append(shifted)
            labels.append(data["labels"].astype(np.int64))
            logits.append(data["logits"])
        row += size
    return {"x": features, "y": np.concatenate(labels), "clips": np.concatenate(clips), "base_logits": np.concatenate(logits)}


def take(data, mask):
    return {key: value[mask] for key, value in data.items()}


def split_by_clip(data, val_share, seed):
    """Делит на обучение и проверку по записям (окна одной записи не расходятся) с сохранением долей классов."""
    rng = np.random.default_rng(seed)
    clip_ids, first = np.unique(data["clips"], return_index=True)
    clip_labels = data["y"][first]
    val_clips = []
    for label in np.unique(clip_labels):
        ids = rng.permutation(clip_ids[clip_labels == label])
        val_clips.extend(ids[: max(1, round(len(ids) * val_share))])
    in_val = np.isin(data["clips"], val_clips)
    return take(data, ~in_val), take(data, in_val)


def predict(head, x, device, batch=1024):
    import torch

    head.eval()
    out = []
    with torch.no_grad():
        for start in range(0, len(x), batch):
            chunk = torch.from_numpy(x[start:start + batch].astype(np.float32)).to(device)
            out.append(torch.softmax(head(chunk), dim=1).cpu().numpy())
    return np.concatenate(out)


def score(head, data, device):
    y_true, y_pred = clip_predictions(predict(head, data["x"], device), data["clips"], data["y"])
    return report(y_true, y_pred, EMOTIONS)


def sample_weights(parts, resd_share, balance=1.0, shares=None):
    """Вес примера при наборе батча.

    Классы выравниваются внутри своего датасета: balance=1 даёт равные доли, 0 оставляет доли как в данных.
    RESD получает долю батча resd_share, иначе он терялся бы рядом с Dusha, которая больше в десятки раз.
    """
    weights = []
    for name, data in parts.items():
        counts = np.bincount(data["y"], minlength=len(EMOTIONS)).astype(float)
        per_sample = 1.0 / counts[data["y"]] ** balance
        if shares is not None:
            share = shares[name]          # доли батча заданы явно: так обучаются сразу несколько датасетов
        else:
            share = resd_share if name == "resd" else 1.0 - resd_share
            if len(parts) == 1:
                share = 1.0
        weights.append(per_sample / per_sample.sum() * share)
    return np.concatenate(weights)


def feature_stats(arrays, layer_start, dim, chunk=2048):
    """Среднее и разброс признаков по обучающим наборам. Считается кусками: в float32 всё сразу в память не помещается."""
    total, squares, count = None, None, 0
    for x in arrays:
        for start in range(0, len(x), chunk):
            part = x[start:start + chunk, layer_start:, :dim].astype(np.float64)
            if total is None:
                total = np.zeros(part.shape[1:])
                squares = np.zeros(part.shape[1:])
            total += part.sum(axis=0)
            squares += (part ** 2).sum(axis=0)
            count += len(part)
    mean = total / count
    std = np.sqrt(np.maximum(squares / count - mean ** 2, 0.0))
    return mean.astype(np.float32), std.astype(np.float32)


def train_head(parts, val, layers="all", pooling="meanstd", hidden=256, dropout=0.3, epochs=40, lr=1e-3, weight_decay=1e-4,
               batch_size=256, resd_share=0.3, label_smoothing=0.05, feature_noise=0.1, layer_lr_scale=30.0, balance=1.0,
               select_on="dusha", seed=0, device=None, log=print, shares=None):
    """parts: обучающие наборы по именам dusha и resd. val: проверочные наборы с теми же именами.

    Возвращает (голова, её конфигурация, история F1 по эпохам). В голове остаются веса лучшей эпохи.
    """
    import torch

    device = device or pick_device()
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)

    arrays = [p["x"] for p in parts.values()]
    y = np.concatenate([p["y"] for p in parts.values()])
    n_layers_total, full_dim = arrays[0].shape[1], arrays[0].shape[2]
    dim = full_dim if pooling == "meanstd" else full_dim // 2
    layer_start = 0 if layers == "all" else n_layers_total - 1
    config = {"n_layers": n_layers_total - layer_start, "dim": dim, "hidden": hidden, "n_classes": len(EMOTIONS),
              "dropout": dropout, "layer_start": layer_start}
    head = build_head(**config)
    mean, std = feature_stats(arrays, layer_start, dim)
    head.mean.copy_(torch.from_numpy(mean))
    head.std.copy_(torch.from_numpy(std + 1e-5))
    head.to(device)

    weights = sample_weights(parts, resd_share, balance, shares)
    steps_per_epoch = max(1, len(y) // batch_size)
    # Веса слоёв: всего 25 чисел под softmax. С общим шагом они почти не сдвигаются с равномерных,
    # поэтому им дан свой шаг, в layer_lr_scale раз больше.
    groups = [
        {"params": head.net.parameters(), "lr": lr, "weight_decay": weight_decay},
        {"params": [head.layer_logits], "lr": lr * layer_lr_scale, "weight_decay": 0.0},
    ]
    optimizer = torch.optim.Adam(groups)
    total_steps = epochs * steps_per_epoch
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer, max_lr=[lr, lr * layer_lr_scale], total_steps=total_steps,
        pct_start=min(0.5, max(0.1, 3 / total_steps)),  # на совсем коротком обучении разгон не короче трёх шагов
    )
    # Признаки нормируются один раз и целиком лежат на устройстве в половинной точности.
    # Шаг обучения тогда сводится к выборке батча, взвешенной сумме слоёв и маленькой сети.
    z_device = torch.empty((len(y), config["n_layers"], dim), dtype=torch.float16, device=device)
    row = 0
    with torch.no_grad():
        for x in arrays:
            for start in range(0, len(x), 2048):
                chunk = torch.from_numpy(x[start:start + 2048].astype(np.float32)).to(device)
                z_device[row:row + len(chunk)] = head.normalize(chunk).half()
                row += len(chunk)
    y_device = torch.from_numpy(y).to(device)
    loss_fn = torch.nn.CrossEntropyLoss(label_smoothing=label_smoothing)

    history, best, best_state = [], -1.0, None
    for epoch in range(1, epochs + 1):
        head.train()
        losses = []
        for _ in range(steps_per_epoch):
            index = torch.from_numpy(rng.choice(len(y), size=batch_size, p=weights)).to(device)
            pooled = head.pool(z_device[index].float())
            if feature_noise:
                # Шум в признаках в долях их разброса: дешёвая замена аугментации звука при замороженном кодировщике.
                pooled = pooled + feature_noise * torch.randn_like(pooled) * pooled.std(dim=0, keepdim=True)
            loss = loss_fn(head.net(pooled), y_device[index])
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            scheduler.step()
            losses.append(loss.item())
        scores = {name: score(head, data, device)["macro_f1"] for name, data in val.items()}
        # Лучшая эпоха выбирается по select_on. По умолчанию это Dusha: проверочная часть RESD взята из данных,
        # на которых учился сам кодировщик, F1 на ней близок к единице и ничего не различает.
        if isinstance(select_on, (tuple, list)):
            mean_score = float(np.mean([scores[name] for name in select_on]))
        else:
            mean_score = scores[select_on] if select_on in scores else float(np.mean(list(scores.values())))
        history.append({"epoch": epoch, "loss": round(float(np.mean(losses)), 4), **scores, "mean": round(mean_score, 4)})
        if mean_score > best:
            best = mean_score
            best_state = {k: v.detach().clone() for k, v in head.state_dict().items()}
        if epoch == 1 or epoch % 5 == 0 or epoch == epochs:
            log("  эпоха %-3d loss %.4f  F1: %s" % (epoch, np.mean(losses), "  ".join(f"{k} {v:.4f}" for k, v in scores.items())))
    head.load_state_dict(best_state)
    return head, config, history


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dusha", required=True, help="признаки обучающей части Dusha")
    parser.add_argument("--resd", required=True, help="признаки обучающей части RESD")
    parser.add_argument("--out", default="speech_analysis/weights/emotion_head.pt")
    parser.add_argument("--layers", choices=["all", "last"], default="all")
    parser.add_argument("--pooling", choices=["mean", "meanstd"], default="meanstd")
    parser.add_argument("--hidden", type=int, default=256)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--resd-share", type=float, default=0.3)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-false-alarm", type=float, default=0.1,
                        help="допустимая доля нейтральных записей, названных отрицательной эмоцией; по ней подбирается порог")
    args = parser.parse_args(argv)

    dusha_train, dusha_val = split_by_clip(load_set(args.dusha), 0.1, args.seed)
    resd_train, resd_val = split_by_clip(load_set(args.resd), 0.15, args.seed)
    head, config, history = train_head(
        {"dusha": dusha_train, "resd": resd_train}, {"dusha": dusha_val, "resd": resd_val},
        layers=args.layers, pooling=args.pooling, hidden=args.hidden, epochs=args.epochs, lr=args.lr, resd_share=args.resd_share, seed=args.seed,
    )
    best = max(history, key=lambda h: h["mean"])

    # Порог для отрицательных эмоций подбирается на проверочной части Dusha, тестовая выборка не участвует.
    device = next(head.parameters()).device
    y_true, pooled = clip_probabilities(predict(head, dusha_val["x"], device), dusha_val["clips"], dusha_val["y"])
    curve = threshold_curve(y_true, pooled, EMOTIONS)
    threshold = pick_threshold(curve, args.max_false_alarm)
    print("порог для отрицательных эмоций:", threshold)
    for row in curve:
        print("  ", row)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    meta = {"labels": EMOTIONS, "val": best, "preprocess": "norm", "negative_threshold": threshold}
    save_head(head.cpu(), args.out, config, meta)
    print("лучшая эпоха:", json.dumps(best, ensure_ascii=False))
    print("веса сохранены в", args.out)


if __name__ == "__main__":
    main()
