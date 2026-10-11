"""Полное дообучение модели эмоций: размораживаются верхние слои кодировщика WavLM.

Это тяжёлый вариант для видеокарты с CUDA. Лёгкий вариант, который обучается за минуту
на готовых признаках, лежит в train_head.py; начинать стоит с него.

Инструменты со слайда «Обучение модели»: PyTorch, предобученные веса
Aniemore/wavlm-emotion-russian-resd, категориальная перекрёстная энтропия, оптимизатор Adam,
F1-мера после каждой эпохи.

Пример на parquet-файлах с Hugging Face (xbgoose/dusha и Aniemore/resd):
    python -m training.train_emotion \\
        --dusha "data/dusha/data/train-*.parquet" --resd "data/resd/data/train-*.parquet" \\
        --unfreeze-layers 4 --epochs 8 --output models/wavlm-emotion-dusha

Пример на исходной раскладке Dusha (TSV и каталог wav):
    python -m training.train_emotion --dusha dusha/crowd_train/raw_crowd_train.tsv --audio-root dusha/crowd_train ...

После обучения укажите каталог с весами в EMOTION_MODEL и поставьте EMOTION_BACKEND=aniemore.
"""
import argparse
import csv
import glob
import json
import random
from pathlib import Path

import numpy as np

from speech_analysis.audio import SAMPLE_RATE, AudioError, load_audio
from speech_analysis.emotion_head import EMOTIONS, pick_device

from .evaluate import report
from .metrics import macro_f1

BASE_MODEL = "Aniemore/wavlm-emotion-russian-resd"

# В Dusha четыре эмоции, у модели Aniemore семь классов.
DUSHA_TO_MODEL = {"angry": "anger", "sad": "sadness", "neutral": "neutral", "positive": "happiness"}


def read_manifest(path, audio_root=None, limit=None):
    """Читает разметку Dusha (TSV или JSONL) и возвращает пары (путь к аудио, метка модели).

    Берётся согласованная метка golden_emo или speaker_emo, а если их нет, поле emotion.
    Записи с меткой other и без метки пропускаются.
    """
    path = Path(path)
    root = Path(audio_root) if audio_root else path.parent
    if path.suffix == ".jsonl":
        rows = (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    else:
        rows = csv.DictReader(path.open(encoding="utf-8"), delimiter="\t")
    items = []
    seen = set()
    for row in rows:
        raw = row.get("golden_emo") or row.get("speaker_emo") or row.get("emotion") or ""
        label = DUSHA_TO_MODEL.get(str(raw).strip().lower())
        audio = row.get("audio_path")
        if label is None or not audio or audio in seen:
            continue
        seen.add(audio)
        items.append((root / audio, label))
        if limit and len(items) >= limit:
            break
    return items


def read_parquet(pattern, limit=None):
    """Пары (байты wav, метка модели) из parquet-файлов Hugging Face."""
    from .extract_features import read_clips

    paths = sorted(glob.glob(pattern))
    if not paths:
        raise FileNotFoundError(f"нет файлов: {pattern}")
    return [(blob, EMOTIONS[label]) for blob, label in read_clips(paths, limit) if label >= 0]


def read_source(source, audio_root=None, limit=None):
    if source.endswith(".parquet"):
        return read_parquet(source, limit)
    return read_manifest(source, audio_root, limit)


def split_items(items, val_share, seed):
    """Делит записи на обучение и проверку с сохранением долей классов."""
    rng = random.Random(seed)
    by_label = {}
    for item in items:
        by_label.setdefault(item[1], []).append(item)
    train, val = [], []
    for label in sorted(by_label):
        group = by_label[label]
        rng.shuffle(group)
        cut = max(1, round(len(group) * val_share))
        val.extend(group[:cut])
        train.extend(group[cut:])
    return train, val


def load_clip(source):
    if isinstance(source, (bytes, bytearray)):
        from .extract_features import decode

        samples = decode(bytes(source))
        if len(samples) < 0.3 * SAMPLE_RATE:
            raise AudioError("слишком короткая запись")
        return samples
    return load_audio(source)


def augment(samples, rng):
    """Случайное усиление и шум. Телефонные записи отличаются от датасета именно уровнем и фоном."""
    samples = samples * (10 ** (rng.uniform(-6, 6) / 20))
    if rng.random() < 0.5:
        power = float(np.mean(samples ** 2)) + 1e-10
        snr_db = rng.uniform(15, 30)
        samples = samples + rng.normal(0, np.sqrt(power / 10 ** (snr_db / 10)), len(samples))
    return np.clip(samples, -1.0, 1.0).astype(np.float32)


def crop(samples, max_seconds, rng=None):
    size = int(max_seconds * SAMPLE_RATE)
    if len(samples) <= size:
        return samples
    start = int(rng.integers(0, len(samples) - size)) if rng is not None else 0
    return samples[start:start + size]


def encode_batch(batch, extractor, label2id, max_seconds, rng=None):
    """rng задан при обучении: тогда запись обрезается в случайном месте и аугментируется."""
    import torch

    clips, labels = [], []
    for source, label in batch:
        try:
            samples = crop(load_clip(source), max_seconds, rng)
        except Exception:
            continue  # битые и слишком короткие файлы в Dusha встречаются
        clips.append(augment(samples, rng) if rng is not None else samples)
        labels.append(label2id[label])
    if not clips:
        return None, None
    inputs = extractor(clips, sampling_rate=SAMPLE_RATE, return_tensors="pt", padding=True, return_attention_mask=True)
    return inputs, torch.tensor(labels)


def freeze(model, unfreeze_layers):
    """Оставляет обучаемыми голову и верхние слои трансформера. Свёрточная часть заморожена всегда."""
    for parameter in model.parameters():
        parameter.requires_grad = False
    for module in (model.projector, model.classifier):
        for parameter in module.parameters():
            parameter.requires_grad = True
    layers = model.wavlm.encoder.layers
    for layer in list(layers)[len(layers) - unfreeze_layers:] if unfreeze_layers else []:
        for parameter in layer.parameters():
            parameter.requires_grad = True
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def balanced_weights(parts, resd_share):
    """Вес записи: классы выравниваются внутри датасета, RESD получает заданную долю батча."""
    weights = []
    for name, items in parts.items():
        counts = {}
        for _, label in items:
            counts[label] = counts.get(label, 0) + 1
        raw = np.array([1.0 / counts[label] for _, label in items])
        share = 1.0 if len(parts) == 1 else (resd_share if name == "resd" else 1.0 - resd_share)
        weights.append(raw / raw.sum() * share)
    return np.concatenate(weights)


def evaluate(model, extractor, items, label2id, batch_size, max_seconds, device):
    import torch

    model.eval()
    y_true, y_pred = [], []
    ordered = sorted(items, key=lambda item: len(item[0]) if isinstance(item[0], (bytes, bytearray)) else 0)
    with torch.no_grad():
        for start in range(0, len(ordered), batch_size):
            inputs, labels = encode_batch(ordered[start:start + batch_size], extractor, label2id, max_seconds)
            if inputs is None:
                continue
            logits = model(**{k: v.to(device) for k, v in inputs.items()}).logits
            y_true.extend(labels.tolist())
            y_pred.extend(logits.argmax(dim=1).cpu().tolist())
    return y_true, y_pred


def train(parts, val, model, extractor, output, epochs=8, lr=2e-5, batch_size=8, accumulate=2, max_seconds=8.0,
          unfreeze_layers=4, resd_share=0.3, label_smoothing=0.05, warmup=0.1, patience=3, steps_per_epoch=None,
          seed=42, device=None, log=print):
    """Дообучает модель и сохраняет веса лучшей по F1 эпохи.

    parts и val: словари «имя датасета -> список (источник звука, метка)». Имена dusha и resd.
    Возвращает историю: по словарю на эпоху с F1 на каждом проверочном наборе.
    """
    import torch

    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    device = device or pick_device()
    model.to(device)
    trainable = freeze(model, unfreeze_layers)
    log(f"обучаемых параметров: {trainable / 1e6:.1f} млн, устройство: {device}")

    label2id = {str(label).lower(): int(index) for label, index in model.config.label2id.items()}
    items = [item for part in parts.values() for item in part]
    weights = balanced_weights(parts, resd_share)
    steps_per_epoch = steps_per_epoch or max(1, len(items) // batch_size)
    total_updates = max(1, epochs * steps_per_epoch // accumulate)

    loss_fn = torch.nn.CrossEntropyLoss(label_smoothing=label_smoothing)
    optimizer = torch.optim.Adam([p for p in model.parameters() if p.requires_grad], lr=lr)
    warmup_updates = max(1, int(total_updates * warmup))
    schedule = lambda step: min((step + 1) / warmup_updates, max(0.0, (total_updates - step) / max(1, total_updates - warmup_updates)))
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, schedule)
    use_amp = device == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    history, best, stale = [], -1.0, 0
    log("Epoch  Loss    F1-Score")
    for epoch in range(1, epochs + 1):
        model.train()
        losses = []
        optimizer.zero_grad()
        for step in range(1, steps_per_epoch + 1):
            index = rng.choice(len(items), size=batch_size, p=weights)
            inputs, labels = encode_batch([items[i] for i in index], extractor, label2id, max_seconds, rng)
            if inputs is None:
                continue
            with torch.autocast("cuda", enabled=use_amp):
                logits = model(**{k: v.to(device) for k, v in inputs.items()}).logits
                loss = loss_fn(logits.float(), labels.to(device))
            scaler.scale(loss / accumulate).backward()
            losses.append(loss.item())
            if step % accumulate == 0 or step == steps_per_epoch:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad()
                scheduler.step()

        scores = {}
        for name, val_items in val.items():
            y_true, y_pred = evaluate(model, extractor, val_items, label2id, batch_size, max_seconds, device)
            scores[name] = macro_f1(y_true, y_pred)
        mean_score = float(np.mean(list(scores.values())))
        history.append({"epoch": epoch, "loss": float(np.mean(losses)) if losses else float("nan"), **scores, "mean": mean_score})
        detail = "  ".join(f"{name} {value:.4f}" for name, value in scores.items())
        log(f"{epoch:<6} {history[-1]['loss']:<7.4f} {mean_score:.4f}   ({detail})")

        if mean_score > best:
            best, stale = mean_score, 0
            Path(output).mkdir(parents=True, exist_ok=True)
            model.save_pretrained(output)
            extractor.save_pretrained(output)
        else:
            stale += 1
            if stale >= patience:
                log(f"F1 не растёт {patience} эпохи подряд, обучение остановлено")
                break
    return history


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dusha", required=True, help="обучающая часть Dusha: шаблон parquet-файлов или TSV/JSONL с разметкой")
    parser.add_argument("--resd", help="обучающая часть RESD в parquet; без неё модель разучится узнавать страх, отвращение и интерес")
    parser.add_argument("--audio-root", help="каталог, от которого отсчитываются audio_path в TSV")
    parser.add_argument("--test-dusha", help="тестовая часть Dusha для итогового замера")
    parser.add_argument("--test-resd", help="тестовая часть RESD для итогового замера")
    parser.add_argument("--base-model", default=BASE_MODEL)
    parser.add_argument("--output", default="models/wavlm-emotion-dusha")
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--accumulate", type=int, default=2)
    parser.add_argument("--unfreeze-layers", type=int, default=4)
    parser.add_argument("--max-seconds", type=float, default=8.0)
    parser.add_argument("--resd-share", type=float, default=0.3)
    parser.add_argument("--limit", type=int, help="взять только первые N записей каждого датасета, для пробного запуска")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

    parts, val = {}, {}
    parts["dusha"], val["dusha"] = split_items(read_source(args.dusha, args.audio_root, args.limit), 0.1, args.seed)
    if args.resd:
        parts["resd"], val["resd"] = split_items(read_source(args.resd, limit=args.limit), 0.15, args.seed)
    print({name: len(items) for name, items in parts.items()}, "записей для обучения")

    model = AutoModelForAudioClassification.from_pretrained(args.base_model)
    extractor = AutoFeatureExtractor.from_pretrained(args.base_model)
    train(parts, val, model, extractor, args.output, epochs=args.epochs, lr=args.lr, batch_size=args.batch_size,
          accumulate=args.accumulate, max_seconds=args.max_seconds, unfreeze_layers=args.unfreeze_layers,
          resd_share=args.resd_share, seed=args.seed)

    best = AutoModelForAudioClassification.from_pretrained(args.output).to(pick_device())
    label2id = {str(label).lower(): int(index) for label, index in best.config.label2id.items()}
    for name, source in (("dusha", args.test_dusha), ("resd", args.test_resd)):
        if source:
            y_true, y_pred = evaluate(best, extractor, read_source(source, limit=args.limit), label2id,
                                      args.batch_size, args.max_seconds, pick_device())
            result = report(y_true, y_pred, EMOTIONS)
            print(f"тест {name}: accuracy {result['accuracy']}  macro-F1 {result['macro_f1']}  UAR {result['uar']}")
    print(f"Лучшие веса сохранены в {args.output}")


if __name__ == "__main__":
    main()
