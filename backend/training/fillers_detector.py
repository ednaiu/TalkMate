"""Детектор звуков-пауз («um», «uh», «э-э») по звуку, а не по расшифровке.

Модели распознавания учат писать «чистый» текст, поэтому звуки-паузы они часто теряют: GigaAM находит
49% русских «э-э», английская Parakeet на живой речи их тоже опускает. Детектор слушает сам звук.

Устройство: тот же замороженный кодировщик WavLM, что и у модели эмоций, и маленькая голова поверх
(та же build_head, два класса: звук-пауза или нет). В приложении кодировщик уже загружен ради эмоций,
поэтому детектор почти ничего не добавляет к времени разбора.

Данные: PodcastFillers (Zhu, Caceres, Salamon, Interspeech 2022): 199 эпизодов подкастов, 145 часов,
около 35 тыс. размеченных «uh» и «um» и около 50 тыс. других событий (дыхание, смех, музыка, обычные слова),
с которыми звуки-паузы нельзя путать. Разметка под некоммерческой лицензией: для учебного проекта подходит,
для коммерческого продукта модель нужно переобучить на разрешённых данных.

Окно признака: 1 секунда вокруг события, но кодировщик слышит запись с запасом по 1,5 секунды с каждой
стороны, а признак берётся по кадрам центральной секунды. Так обучение совпадает с работой в приложении,
где кадры одной секунды вырезаются из длинного окна.

Запуск по шагам (Kaggle, бесплатная T4): training/kaggle/fillers_detector.ipynb.

    python -m training.fillers_detector extract --csv PodcastFillers.csv --split train --out data/fillers/train.npz
    python -m training.fillers_detector train --train data/fillers/train.npz --val data/fillers/validation.npz \\
        --out speech_analysis/weights/filler_head.pt
    python -m training.fillers_detector evaluate --data data/fillers/test.npz --head speech_analysis/weights/filler_head.pt
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from speech_analysis.audio import SAMPLE_RATE

FILLER_LABELS = {"Uh", "Um"}
# Классы, на которых учили FillerNet. «None» в разметке означает событие вне этого набора.
KNOWN_LABELS = {"Uh", "Um", "Words", "Breath", "Laughter", "Music"}
CONTEXT_SEC = 1.5
CENTER_SEC = 1.0
FRAME_SEC = 0.02          # шаг кадров WavLM: 320 отсчётов при 16 кГц
DEFAULT_ENCODER = "Aniemore/wavlm-emotion-russian-resd"
AUDIO_REPO = "ylacombe/podcast_fillers"   # звук эпизодов на Hugging Face; разметка берётся с Zenodo


SPLIT_ALIASES = {"val": "validation", "valid": "validation", "dev": "validation"}


def _norm_label(value):
    value = (value or "").strip()
    return value[:1].upper() + value[1:].lower() if value else "None"


def _norm_split(value):
    value = (value or "").strip().lower()
    return SPLIT_ALIASES.get(value, value)


def read_annotations(path, split):
    """События одного разбиения: {эпизод: [(начало секунды-клипа в эпизоде, метка), ...]}.

    Если не найдено ни одного события, бросает ошибку с тем, что лежит в файле: так сразу видно,
    скачалась ли разметка и как в ней названы столбцы и разбиения."""
    events = defaultdict(list)
    seen_splits, seen_labels, header = defaultdict(int), defaultdict(int), None
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames
        for row in reader:
            label = _norm_label(row.get("consolidated_label"))
            row_split = _norm_split(row.get("episode_split_subset"))
            seen_splits[row_split] += 1
            seen_labels[label] += 1
            if label not in KNOWN_LABELS or row_split != split:
                continue
            events[row["podcast_filename"].strip()].append((float(row["clip_start_inepisode"]), label))
    if not events:
        raise ValueError(f"В разметке {path} нет событий для разбиения {split}. Столбцы: {header}; "
                         f"разбиения: {dict(seen_splits)}; метки: {dict(seen_labels)}")
    return dict(events)


def balance(events, negatives_per_filler=1.5, seed=0):
    """Оставляет все звуки-паузы и не больше negatives_per_filler других событий на каждую из них."""
    rng = np.random.default_rng(seed)
    flat = [(episode, start, label) for episode, items in events.items() for start, label in items]
    fillers = [item for item in flat if item[2] in FILLER_LABELS]
    others = [item for item in flat if item[2] not in FILLER_LABELS]
    keep = min(len(others), int(round(len(fillers) * negatives_per_filler)))
    picked = [others[i] for i in rng.choice(len(others), size=keep, replace=False)] if keep else []
    result = defaultdict(list)
    for episode, start, label in fillers + picked:
        result[episode].append((start, label))
    return {episode: sorted(items) for episode, items in result.items()}


def episode_key(name):
    """Ключ для сравнения имён эпизодов: без расширения, регистра, кавычек, тире и лишних знаков."""
    import unicodedata

    name = Path(name).name
    if Path(name).suffix.lower() in (".mp3", ".wav", ".flac", ".m4a"):
        name = name[: -len(Path(name).suffix)]
    name = unicodedata.normalize("NFKC", name).casefold()
    return "".join(ch for ch in name if ch.isalnum())


def match_episodes(names, repo_files):
    """Соответствие имени эпизода из разметки файлу со звуком: по имени файла, без учёта регистра и знаков."""
    by_key = {}
    for path in repo_files:
        if Path(path).suffix.lower() in (".mp3", ".wav", ".flac", ".m4a"):
            by_key.setdefault(episode_key(path), path)
    return {name: by_key[episode_key(name)] for name in names if episode_key(name) in by_key}


def context_window(samples, clip_start, context=CONTEXT_SEC, center=CENTER_SEC):
    """Кусок записи с запасом вокруг секунды-клипа и положение этой секунды внутри куска (в секундах)."""
    start = max(0.0, clip_start - context)
    end = min(len(samples) / SAMPLE_RATE, clip_start + center + context)
    piece = samples[int(start * SAMPLE_RATE):int(end * SAMPLE_RATE)]
    offset = clip_start - start
    return piece, offset, offset + center


def frame_range(center_start, center_end, n_frames, frame=FRAME_SEC):
    """Номера кадров кодировщика, покрывающих центральную секунду."""
    first = int(np.floor(center_start / frame))
    last = int(np.ceil(center_end / frame))
    first = min(max(first, 0), max(n_frames - 1, 0))
    last = min(max(last, first + 1), n_frames)
    return first, last


def pool_frames(hidden_states, first, last):
    """Признак по кадрам [first, last): для каждого слоя среднее и отклонение. hidden_states: [слои, кадры, размер]."""
    part = hidden_states[:, first:last, :]
    mean = part.mean(axis=1)
    std = np.sqrt(np.maximum(part.var(axis=1), 1e-8))
    return np.concatenate([mean, std], axis=-1)


def encode_centers(model, extractor, pieces, centers):
    """Прогон кусков через кодировщик; признак каждого берётся по кадрам его центральной секунды."""
    import torch

    device = next(model.parameters()).device
    inputs = extractor(pieces, sampling_rate=SAMPLE_RATE, return_tensors="pt", padding=True, return_attention_mask=True)
    with torch.inference_mode(), torch.autocast(device_type="cuda", enabled=device.type == "cuda"):
        out = model.wavlm(inputs["input_values"].to(device), attention_mask=inputs["attention_mask"].to(device),
                          output_hidden_states=True)
    states = torch.stack(out.hidden_states, dim=1).float()   # [B, слои, кадры, размер]
    features = []
    for index, (start, end) in enumerate(centers):
        n_frames = int(round(len(pieces[index]) / SAMPLE_RATE / FRAME_SEC))
        first, last = frame_range(start, end, min(n_frames, states.shape[2]))
        part = states[index, :, first:last, :]
        mean = part.mean(dim=1)
        std = part.var(dim=1, unbiased=False).clamp(min=1e-8).sqrt()
        features.append(torch.cat([mean, std], dim=-1).cpu().numpy().astype(np.float16))
    return features


def extract(csv_path, split, out, encoder=DEFAULT_ENCODER, negatives_per_filler=1.5, max_episodes=None, batch=16, log=print):
    """Признаки событий одного разбиения. Звук эпизода скачивается, разбирается и сразу удаляется."""
    import librosa
    from huggingface_hub import HfApi, hf_hub_download

    from speech_analysis.emotion_head import load_encoder

    events = read_annotations(csv_path, split)
    if split == "train" and negatives_per_filler:
        events = balance(events, negatives_per_filler)
    repo_files = HfApi().list_repo_files(AUDIO_REPO, repo_type="dataset")
    files = match_episodes(events, repo_files)
    missing = sorted(set(events) - set(files))
    log(f"{split}: эпизодов в разметке {len(events)}, найден звук для {len(files)}")
    if missing:
        log(f"нет звука для {len(missing)} эпизодов, например {missing[:3]}")
    if not files:
        audio = [f for f in repo_files if Path(f).suffix.lower() in (".mp3", ".wav", ".flac", ".m4a")]
        raise ValueError(f"Ни один эпизод не сопоставлен со звуком. В разметке: {sorted(events)[:3]}; "
                         f"в {AUDIO_REPO} ({len(audio)} файлов): {audio[:3]}")
    model, extractor = load_encoder(encoder)
    features, labels, fine, episodes = [], [], [], []
    names = sorted(files)[:max_episodes] if max_episodes else sorted(files)
    for number, name in enumerate(names):
        local = hf_hub_download(AUDIO_REPO, files[name], repo_type="dataset")
        samples, _ = librosa.load(local, sr=SAMPLE_RATE, mono=True)
        Path(local).unlink(missing_ok=True)
        items = events[name]
        for start in range(0, len(items), batch):
            chunk = items[start:start + batch]
            windows = [context_window(samples, clip_start) for clip_start, _ in chunk]
            features += encode_centers(model, extractor, [w[0] for w in windows], [(w[1], w[2]) for w in windows])
            labels += [int(label in FILLER_LABELS) for _, label in chunk]
            fine += [label for _, label in chunk]
            episodes += [number] * len(chunk)
        log(f"{split}: эпизод {number + 1}/{len(names)}, событий {len(items)}, всего {len(labels)}")
    if not features:
        raise ValueError(f"{split}: не извлечено ни одного признака")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    np.savez(out, features=np.stack(features), labels=np.array(labels, dtype=np.int64), fine=np.array(fine),
             episodes=np.array(episodes, dtype=np.int64))
    return len(labels)


def window_starts(duration, center=CENTER_SEC, hop=0.25):
    """Начала окон по секунде с шагом hop, последнее окно прижато к концу записи."""
    if duration <= center:
        return [0.0]
    starts = list(np.arange(0.0, duration - center, hop))
    if duration - center - starts[-1] > 1e-6:
        starts.append(duration - center)
    return [round(float(s), 3) for s in starts]


def merge_detections(starts, scores, threshold, center=CENTER_SEC):
    """Окна выше порога, слитые в события: [(начало, конец, наибольшая уверенность)]."""
    events = []
    for start, score in zip(starts, scores):
        if score < threshold:
            continue
        end = start + center
        if events and start <= events[-1][1]:
            first, _, best = events[-1]
            events[-1] = (first, end, max(best, float(score)))
        else:
            events.append((start, end, float(score)))
    return events


def scan(model, extractor, head, samples, threshold, piece_sec=8.0, hop=0.25):
    """Звуки-паузы в записи. Кодировщик прогоняется по кускам до 8 секунд с запасом CONTEXT_SEC по краям,
    признак каждого секундного окна берётся из кадров куска, как при обучении."""
    import torch

    device = next(head.parameters()).device
    duration = len(samples) / SAMPLE_RATE
    starts = window_starts(duration, hop=hop)
    scores = np.zeros(len(starts))
    piece_start = 0.0
    while piece_start < duration:
        piece_end = min(duration, piece_start + piece_sec)
        # Окно относится к куску, в котором начинается; его хвост укладывается в запас CONTEXT_SEC за краем куска.
        inside = [i for i, s in enumerate(starts) if piece_start <= s < piece_end or (piece_end >= duration and s >= piece_start)]
        lo, hi = max(0.0, piece_start - CONTEXT_SEC), min(duration, piece_end + CONTEXT_SEC)
        piece = samples[int(lo * SAMPLE_RATE):int(hi * SAMPLE_RATE)]
        if inside:
            centers = [(starts[i] - lo, min(starts[i] + CENTER_SEC, duration) - lo) for i in inside]
            feats = _encode_many(model, extractor, piece, centers)
            with torch.inference_mode():
                logits = head(torch.from_numpy(np.stack(feats).astype(np.float32)).to(device))
                values = torch.softmax(logits, dim=-1)[:, 1].cpu().numpy()
            scores[inside] = values
        piece_start = piece_end
    return merge_detections(starts, scores, threshold)


def _encode_many(model, extractor, piece, centers):
    """Один прогон куска и признаки для нескольких секундных окон внутри него."""
    import torch

    device = next(model.parameters()).device
    inputs = extractor([piece], sampling_rate=SAMPLE_RATE, return_tensors="pt", return_attention_mask=True)
    with torch.inference_mode(), torch.autocast(device_type="cuda", enabled=device.type == "cuda"):
        out = model.wavlm(inputs["input_values"].to(device), attention_mask=inputs["attention_mask"].to(device),
                          output_hidden_states=True)
    states = torch.stack(out.hidden_states, dim=1)[0].float().cpu().numpy()   # [слои, кадры, размер]
    result = []
    for start, end in centers:
        first, last = frame_range(start, end, states.shape[1])
        result.append(pool_frames(states, first, last).astype(np.float16))
    return result


def metrics(y_true, scores, threshold):
    y_true = np.asarray(y_true).astype(bool)
    predicted = np.asarray(scores) >= threshold
    tp = int((predicted & y_true).sum())
    fp = int((predicted & ~y_true).sum())
    fn = int((~predicted & y_true).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"threshold": round(float(threshold), 3), "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def pick_threshold(y_true, scores, min_precision=0.9):
    """Порог с наибольшей полнотой при точности не ниже min_precision: лишний упрёк хуже пропуска.
    Если такой точности не достичь, берётся порог с лучшей F1."""
    candidates = [metrics(y_true, scores, t) for t in np.linspace(0.05, 0.95, 91)]
    good = [c for c in candidates if c["precision"] >= min_precision]
    if good:
        return max(good, key=lambda c: (c["recall"], c["precision"]))
    return max(candidates, key=lambda c: c["f1"])


def per_label_recall(fine, scores, threshold):
    """Какую долю событий каждого вида детектор назвал звуком-паузой."""
    fine = np.asarray(fine)
    return {str(label): round(float((np.asarray(scores)[fine == label] >= threshold).mean()), 4) for label in sorted(set(fine))}


def _scores(head, x, device, batch=2048):
    import torch

    out = []
    with torch.inference_mode():
        for start in range(0, len(x), batch):
            logits = head(torch.from_numpy(x[start:start + batch].astype(np.float32)).to(device))
            out.append(torch.softmax(logits, dim=-1)[:, 1].cpu().numpy())
    return np.concatenate(out)


def train(train_path, val_path, out, hidden=256, dropout=0.3, epochs=30, lr=1e-3, weight_decay=1e-4, batch=256,
          min_precision=0.9, seed=0, log=print):
    import torch
    from torch import nn

    from speech_analysis.emotion_head import build_head, pick_device, save_head

    torch.manual_seed(seed)
    device = pick_device()
    tr, va = np.load(train_path), np.load(val_path)
    x, y = tr["features"], tr["labels"]
    n_layers, dim = x.shape[1], x.shape[2]
    config = {"n_layers": n_layers, "dim": dim, "hidden": hidden, "n_classes": 2, "dropout": dropout}
    head = build_head(**config).to(device)
    head.mean.copy_(torch.from_numpy(x.astype(np.float32).mean(axis=0)))
    head.std.copy_(torch.from_numpy(x.astype(np.float32).std(axis=0) + 1e-5))
    counts = np.bincount(y, minlength=2)
    loss_fn = nn.CrossEntropyLoss(weight=torch.tensor(len(y) / (2.0 * np.maximum(counts, 1)), dtype=torch.float32, device=device))
    optimizer = torch.optim.Adam(head.parameters(), lr=lr, weight_decay=weight_decay)
    rng = np.random.default_rng(seed)
    best, best_state = None, None
    for epoch in range(epochs):
        head.train()
        order = rng.permutation(len(y))
        for start in range(0, len(order), batch):
            index = order[start:start + batch]
            logits = head(torch.from_numpy(x[index].astype(np.float32)).to(device))
            loss = loss_fn(logits, torch.from_numpy(y[index]).to(device))
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        head.eval()
        chosen = pick_threshold(va["labels"], _scores(head, va["features"], device), min_precision)
        log(f"эпоха {epoch + 1}: проверка {chosen}")
        if best is None or (chosen["f1"], chosen["recall"]) > (best["f1"], best["recall"]):
            best = chosen
            best_state = {k: v.detach().cpu().clone() for k, v in head.state_dict().items()}
    head.load_state_dict(best_state)
    meta = {"task": "filler", "labels": ["other", "filler"], "threshold": best["threshold"], "val": best,
            "encoder": DEFAULT_ENCODER, "context_sec": CONTEXT_SEC, "center_sec": CENTER_SEC}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    save_head(head.cpu(), out, config, meta)
    return meta


def evaluate(data_path, head_path):
    from speech_analysis.emotion_head import load_head, pick_device

    device = pick_device()
    head, meta = load_head(head_path, device)
    data = np.load(data_path)
    scores = _scores(head, data["features"], device)
    return {"at_val_threshold": metrics(data["labels"], scores, meta["threshold"]),
            "per_label": per_label_recall(data["fine"], scores, meta["threshold"]), "n": int(len(scores))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("extract")
    p.add_argument("--csv", required=True)
    p.add_argument("--split", choices=["train", "validation", "test"], required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--encoder", default=DEFAULT_ENCODER)
    p.add_argument("--negatives-per-filler", type=float, default=1.5)
    p.add_argument("--max-episodes", type=int)
    p = sub.add_parser("train")
    p.add_argument("--train", required=True)
    p.add_argument("--val", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--epochs", type=int, default=30)
    p.add_argument("--min-precision", type=float, default=0.9)
    p = sub.add_parser("evaluate")
    p.add_argument("--data", required=True)
    p.add_argument("--head", required=True)
    p.add_argument("--out")
    args = parser.parse_args(argv)
    if args.command == "extract":
        print(extract(args.csv, args.split, args.out, args.encoder, args.negatives_per_filler, args.max_episodes))
    elif args.command == "train":
        print(json.dumps(train(args.train, args.val, args.out, epochs=args.epochs, min_precision=args.min_precision), ensure_ascii=False, indent=2))
    else:
        result = evaluate(args.data, args.head)
        if args.out:
            Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
