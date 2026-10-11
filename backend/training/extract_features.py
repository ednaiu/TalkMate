"""Прогон записей через замороженный кодировщик с сохранением признаков на диск.

Кодировщик занимает почти всё время обучения, а его веса не меняются. Поэтому признаки
считаются один раз, и дальше любой эксперимент с головой идёт за секунды.

    python -m training.extract_features --parquet data/dusha/data/test-00000-*.parquet --out data/features/dusha_test.npz
"""
import argparse
import glob
import io
import time
from pathlib import Path

import numpy as np

from speech_analysis.audio import SAMPLE_RATE
from speech_analysis.emotion import windows
from speech_analysis.emotion_head import EMOTIONS, encode, load_encoder
from speech_analysis.preprocess import PREPROCESS_MODES as PREPROCESS

# Метки Dusha и RESD приводятся к семи классам модели. other и неизвестные получают -1.
LABELS = {name: index for index, name in enumerate(EMOTIONS)}
LABELS.update({"angry": LABELS["anger"], "sad": LABELS["sadness"], "positive": LABELS["happiness"]})

def decode(blob):
    import librosa
    import soundfile as sf

    samples, rate = sf.read(io.BytesIO(blob), dtype="float32", always_2d=True)
    samples = samples.mean(axis=1)
    if rate != SAMPLE_RATE:
        samples = librosa.resample(samples, orig_sr=rate, target_sr=SAMPLE_RATE)
    return samples


def read_clips(paths, limit=None):
    """Отдаёт (запись, метка) из parquet-файлов в раскладке Hugging Face."""
    import pyarrow.parquet as pq

    count = 0
    for path in paths:
        parquet = pq.ParquetFile(path)
        audio_column = "audio" if "audio" in parquet.schema_arrow.names else "speech"
        for batch in parquet.iter_batches(batch_size=64, columns=[audio_column, "emotion"]):
            for audio, emotion in zip(batch.column(0).to_pylist(), batch.column(1).to_pylist()):
                yield audio["bytes"], LABELS.get(str(emotion).lower(), -1)
                count += 1
                if limit and count >= limit:
                    return


def extract(paths, out, model_id, preprocess="raw", limit=None, batch_seconds=80.0, min_seconds=0.3, log=print, source=None):
    """source: готовый поток пар (байты записи, метка) вместо parquet-файлов в раскладке Dusha."""
    model, extractor = load_encoder(model_id)
    prepare = PREPROCESS[preprocess]

    pieces, labels, clip_ids = [], [], []
    skipped = 0
    for clip_id, (blob, label) in enumerate(source if source is not None else read_clips(paths, limit)):
        try:
            samples = decode(blob)
        except Exception:
            skipped += 1
            continue
        if label < 0 or len(samples) < min_seconds * SAMPLE_RATE:
            skipped += 1
            continue
        for piece in windows(prepare(samples)):
            pieces.append(piece.astype(np.float32))
            labels.append(label)
            clip_ids.append(clip_id)
    log(f"записей: {len(set(clip_ids))}, окон: {len(pieces)}, пропущено: {skipped}")

    # Батчи из окон близкой длины: меньше дополнения тишиной и быстрее прогон.
    order = np.argsort([len(p) for p in pieces])
    features = [None] * len(pieces)
    logits = [None] * len(pieces)
    started = time.time()
    batch, longest = [], 0
    def flush():
        if not batch:
            return
        layer_features, base_logits = encode(model, extractor, [pieces[i] for i in batch])
        for row, index in enumerate(batch):
            features[index] = layer_features[row].astype(np.float16)
            logits[index] = base_logits[row]
    done = 0
    for index in order:
        length = max(longest, len(pieces[index]))
        if batch and length * (len(batch) + 1) > batch_seconds * SAMPLE_RATE:
            flush()
            done += len(batch)
            if done % 2000 < len(batch):
                log(f"  {done}/{len(pieces)} окон, {time.time() - started:.0f} с")
            batch, length = [], len(pieces[index])
        batch.append(index)
        longest = length
    flush()

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    np.savez(out, features=np.stack(features), logits=np.stack(logits), labels=np.array(labels), clips=np.array(clip_ids))
    log(f"сохранено в {out} за {time.time() - started:.0f} с")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--parquet", nargs="+", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--model", default="Aniemore/wavlm-emotion-russian-resd")
    parser.add_argument("--preprocess", choices=sorted(PREPROCESS), default="raw")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(argv)
    paths = sorted(p for pattern in args.parquet for p in glob.glob(pattern))
    if not paths:
        parser.error("не найдено ни одного parquet-файла")
    extract(paths, args.out, args.model, args.preprocess, args.limit)


if __name__ == "__main__":
    main()
