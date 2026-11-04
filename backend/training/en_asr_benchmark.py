"""Замер английского распознавания на спонтанной речи: сколько звуков-пауз и слов-заполнителей сохраняет модель.

Данные: AMI Meeting Corpus, гарнитурные микрофоны (ihm), тестовая часть. Лицензия CC BY 4.0. Расшифровки
AMI дословные: в них есть «um», «mm-hmm», «hmm», повторы и оборванные слова, поэтому по ним видно, что
модель выбрасывает. Берутся реплики от 2 до 20 секунд: все, где есть звук-пауза, и случайная выборка остальных.

Подсчёт идёт теми же правилами, что и в приложении (speech_analysis.fillers, английский язык), но знаки
препинания перед подсчётом убираются у обеих сторон: в AMI их нет. Поэтому «like» и «so», которые приложение
засчитывает только между запятыми, здесь не считаются; считаются звуки-паузы и словосочетания.

    python -m training.en_asr_benchmark --models nemo-parakeet-tdt-0.6b-v3:int8 --limit 600 --out training/results/en_asr_benchmark.json
"""
import argparse
import json
import random
import re
import time
from pathlib import Path

import numpy as np

from speech_analysis import lang
from speech_analysis.audio import SAMPLE_RATE
from speech_analysis.fillers import find_fillers

SOUNDS_EN = ("um", "uh")
PHRASES_EN = ("you know", "i mean", "sort of", "kind of")


def normalize_en(text):
    """Нижний регистр, без знаков препинания, «mm-hmm» и подобное раздельно не режется."""
    text = (text or "").lower().replace("’", "'")
    text = re.sub(r"[^a-z0-9'\- ]+", " ", text)
    text = re.sub(r"(?<![a-z])-|-(?![a-z])", " ", text)
    return " ".join(text.split())


def fillers_en(text):
    with lang.use(speech="en", ui="en"):
        return find_fillers(text)


def matched(reference, hypothesis, only):
    ref = [w for w in fillers_en(reference) if w in only]
    hyp = [w for w in fillers_en(hypothesis) if w in only]
    remaining, hits = list(hyp), 0
    for word in ref:
        if word in remaining:
            remaining.remove(word)
            hits += 1
    return len(ref), hits, len(hyp)


def repetitions(text):
    """Повторы подряд («on on», «the the»): признак дословной расшифровки."""
    words = text.split()
    return sum(1 for a, b in zip(words, words[1:]) if a == b and a.isalpha())


def load_ami(limit=600, seed=0, min_sec=2.0, max_sec=20.0, split="test"):
    """Реплики AMI: все с звуками-паузами и случайные остальные, всего не больше limit."""
    from datasets import load_dataset

    try:
        rows = load_dataset("edinburghcstr/ami", "ihm", split=split)
    except Exception:
        # Новые версии datasets не запускают скрипты загрузки; тогда берём готовую выгрузку Hugging Face в parquet.
        files = f"hf://datasets/edinburghcstr/ami@refs%2Fconvert%2Fparquet/ihm/{split}/*.parquet"
        rows = load_dataset("parquet", data_files={split: files}, split=split)
    rows = rows.filter(lambda r: min_sec <= r["end_time"] - r["begin_time"] <= max_sec)
    texts = [normalize_en(t) for t in rows["text"]]
    with_sounds = [i for i, t in enumerate(texts) if any(w in SOUNDS_EN for w in fillers_en(t))]
    others = [i for i, t in enumerate(texts) if i not in set(with_sounds)]
    random.Random(seed).shuffle(others)
    picked = sorted(with_sounds[: limit // 2] + others[: limit - min(len(with_sounds), limit // 2)])
    items = []
    for i in picked:
        audio = rows[i]["audio"]
        samples = np.asarray(audio["array"], dtype=np.float32)
        if audio["sampling_rate"] != SAMPLE_RATE:
            import librosa

            samples = librosa.resample(samples, orig_sr=audio["sampling_rate"], target_sr=SAMPLE_RATE)
        items.append((samples, texts[i]))
    return items


def evaluate(recognize, items):
    import jiwer

    refs, hyps = [], []
    totals = defaultdict_int()
    seconds, started = 0.0, time.time()
    for samples, reference in items:
        hypothesis = normalize_en(recognize(samples))
        refs.append(reference)
        hyps.append(hypothesis)
        seconds += len(samples) / SAMPLE_RATE
        for key, only in (("sounds", SOUNDS_EN), ("phrases", PHRASES_EN)):
            r, m, h = matched(reference, hypothesis, only)
            totals[f"{key}_ref"] += r
            totals[f"{key}_hit"] += m
            totals[f"{key}_hyp"] += h
        totals["rep_ref"] += repetitions(reference)
        totals["rep_hyp"] += repetitions(hypothesis)
    share = lambda a, b: round(totals[a] / totals[b], 4) if totals[b] else None
    return {
        "n": len(items),
        "audio_minutes": round(seconds / 60, 1),
        "wer": round(jiwer.wer(refs, hyps), 4),
        "sound_recall": share("sounds_hit", "sounds_ref"),
        "sound_precision": share("sounds_hit", "sounds_hyp"),
        "sounds_in_reference": totals["sounds_ref"],
        "phrase_recall": share("phrases_hit", "phrases_ref"),
        "phrases_in_reference": totals["phrases_ref"],
        "repetitions_kept": share("rep_hyp", "rep_ref"),
        "rtf": round((time.time() - started) / seconds, 4) if seconds else None,
    }, list(zip(refs, hyps))


def defaultdict_int():
    from collections import defaultdict

    return defaultdict(int)


def make_recognizer(name):
    """Имя модели onnx-asr, при желании с квантованием через двоеточие: nemo-parakeet-tdt-0.6b-v3:int8."""
    from speech_analysis.recognition import OnnxRecognizer

    model, _, quantization = name.partition(":")
    return OnnxRecognizer(model, quantization=quantization or None).recognize


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+", default=["nemo-parakeet-tdt-0.6b-v3:int8"])
    parser.add_argument("--limit", type=int, default=600)
    parser.add_argument("--out", default="training/results/en_asr_benchmark.json")
    args = parser.parse_args(argv)
    items = load_ami(args.limit)
    results = {}
    for name in args.models:
        try:
            summary, pairs = evaluate(make_recognizer(name), items)
        except Exception as exc:  # одна неудачная модель не должна ронять замер остальных
            results[name] = {"error": str(exc)}
            continue
        results[name] = {**summary, "examples": [p for p in pairs if p[0] != p[1]][:30]}
        print(name, json.dumps(summary, ensure_ascii=False))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
