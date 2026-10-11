"""Признаки английских датасетов эмоций для дообучения головы.

CREMA-D и RAVDESS: актёры читают одни и те же фразы с заданной эмоцией. MELD: реплики из сериала «Друзья»,
речь ближе к живой, со смехом зала и музыкой. Метки приводятся к семи классам модели; удивление пропускается,
такого класса у модели нет.

Проверочные и тестовые части не пересекаются с обучающими по говорящим: в CREMA-D они делятся по номеру актёра,
в RAVDESS взята готовая разбивка по актёрам, в MELD своя разбивка по сериям.

    python -m training.extract_english --data data/en --out data/features
"""
import argparse
import csv
import re
import tarfile
from pathlib import Path

import pyarrow.parquet as pq

from speech_analysis.emotion_head import EMOTIONS

from .extract_features import extract

LABELS = {name: index for index, name in enumerate(EMOTIONS)}
ENGLISH = {
    "anger": "anger", "angry": "anger", "disgust": "disgust", "fear": "fear", "fearful": "fear", "happy": "happiness", "joy": "happiness",
    "neutral": "neutral", "calm": "neutral", "sad": "sadness", "sadness": "sadness",
}


def label_of(name):
    return LABELS[ENGLISH[name]] if name in ENGLISH else -1


def parquet_clips(paths, keep=lambda file: True):
    for path in paths:
        table = pq.ParquetFile(path)
        for batch in table.iter_batches(batch_size=64, columns=["file", "audio", "emotion"]):
            for file, audio, emotion in zip(*(batch.column(i).to_pylist() for i in range(3))):
                if keep(file):
                    yield audio["bytes"], label_of(str(emotion).lower())


def crema_actor(file):
    return int(re.search(r"(\d{4})_[A-Z]{3}_[A-Z]{3}_", file).group(1))


CREMA_PARTS = {"test": lambda actor: actor % 5 == 0, "val": lambda actor: actor % 5 == 1, "train": lambda actor: actor % 5 > 1}


def meld_clips(folder, part):
    """Реплики MELD: метки в csv, звук в архиве под именем dia<диалог>_utt<реплика>.flac."""
    labels = {}
    with open(folder / f"{part}.csv", newline="", encoding="utf-8", errors="replace") as source:
        for row in csv.DictReader(source):
            labels[f"dia{row['Dialogue_ID']}_utt{row['Utterance_ID']}"] = label_of(row["Emotion"].lower())
    with tarfile.open(folder / "archive" / f"{part}.tar.gz") as archive:
        for member in archive:
            if member.isfile() and Path(member.name).stem in labels:
                yield archive.extractfile(member).read(), labels[Path(member.name).stem]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default="data/en")
    parser.add_argument("--out", default="data/features")
    parser.add_argument("--model", default="Aniemore/wavlm-emotion-russian-resd")
    parser.add_argument("--only", nargs="*")
    args = parser.parse_args(argv)
    data, out = Path(args.data), Path(args.out)
    jobs = {}
    crema = sorted((data / "cremad-parquet" / "data").glob("*.parquet"))
    for part, rule in CREMA_PARTS.items():
        jobs[f"crema_{part}"] = lambda rule=rule: parquet_clips(crema, lambda file: rule(crema_actor(file)))
    ravdess = data / "ravdess-parquet" / "fold1"
    jobs["ravdess_train"] = lambda: parquet_clips(sorted(ravdess.glob("train-*.parquet")))
    jobs["ravdess_test"] = lambda: parquet_clips(sorted(ravdess.glob("test-*.parquet")))
    for part in ("dev", "test", "train"):
        jobs[f"meld_{part}"] = lambda part=part: meld_clips(data / "MELD_audio", part)
    for name, source in jobs.items():
        if args.only and name not in args.only:
            continue
        target = out / f"{name}_raw.npz"
        if target.exists():
            print(name, "уже есть")
            continue
        print(name, flush=True)
        extract([], target, args.model, source=source())


if __name__ == "__main__":
    main()
