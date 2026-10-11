"""Сравнение моделей распознавания русской речи на задачах приложения.

Кроме обычной доли ошибок в словах (WER) считаются величины, от которых зависят оценки приложения:
ошибка в числе слов (из него получается темп речи) и полнота по словам-заполнителям.

    python -m training.asr_benchmark --models gigaam-v3-ctc vosk-small --out data/asr_benchmark.json
"""
import argparse
import io
import json
import re
import time
from pathlib import Path

import numpy as np

from speech_analysis.audio import SAMPLE_RATE
from speech_analysis.fillers import find_fillers
from speech_analysis.speed import tokenize

DATASETS = {
    # имя: (файл, сколько записей взять, что это за речь)
    "podlodka": ("data/asr/podlodka_speech/data/test-00000-of-00001.parquet", None, "подкаст, спонтанная речь, записи по 20–60 секунд"),
    "sova": ("data/asr/sova_rudevices/data/test-00000-of-00002-e3baf0fee2116c5f.parquet", 300, "спонтанные короткие реплики, записаны на бытовые устройства"),
    "fleurs": ("data/asr/fleurs/parquet-data/ru_ru/test-00000-of-00001.parquet", 150, "чтение подготовленного текста"),
    # Все реплики из той же части SOVA, где в эталоне записан звук-пауза («ээ», «мм»).
    "hesitations": ("data/asr/sova_rudevices/data/test-00000-of-00002-e3baf0fee2116c5f.parquet", "hesitations", "реплики со звуками-паузами"),
}
SOUNDS = ("э-э", "м-м", "а-а")


def normalize_text(text, keep_hyphens=False):
    """Приводит текст к виду для сравнения: нижний регистр, без пунктуации, числа словами."""
    from num2words import num2words

    text = text.lower().replace("ё", "е")
    text = re.sub(r"\d+", lambda m: " " + num2words(int(m.group()), lang="ru") + " ", text)
    return " ".join(tokenize(text if keep_hyphens else text.replace("-", " ")))


def for_wer(text):
    """Для WER дефисы убираются: «всё-таки» и «все таки» считаются одним и тем же."""
    return text.replace("-", " ")


def load_dataset(name):
    import pyarrow.parquet as pq
    import soundfile as sf

    path, limit, _ = DATASETS[name]
    table = pq.ParquetFile(path).read(columns=["audio", "transcription"]).to_pylist()
    items = []
    only_hesitations = limit == "hesitations"
    for row in (table if only_hesitations else table[:limit]):
        if only_hesitations and not any(f in SOUNDS for f in find_fillers(normalize_text(row["transcription"], keep_hyphens=True))):
            continue
        samples, rate = sf.read(io.BytesIO(row["audio"]["bytes"]), dtype="float32", always_2d=True)
        assert rate == SAMPLE_RATE, rate
        reference = normalize_text(row["transcription"], keep_hyphens=True)
        if reference:
            items.append((samples.mean(axis=1), reference))
    return items


def make_model(name):
    """Возвращает функцию «отсчёты -> текст» для модели-кандидата."""
    from speech_analysis.recognition import OnnxRecognizer, VoskRecognizer

    if name == "vosk-small":
        return VoskRecognizer("models/vosk-model-small-ru-0.22").recognize
    if name.startswith("whisper:"):
        return whisper(name.split(":", 1)[1])
    return OnnxRecognizer(name).recognize


def whisper(model_id):
    import torch
    from transformers import pipeline

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    pipe = pipeline("automatic-speech-recognition", model=model_id, device=device, torch_dtype=torch.float16 if device != "cpu" else torch.float32)

    def recognize(samples):
        result = pipe({"raw": samples, "sampling_rate": SAMPLE_RATE}, chunk_length_s=30,
                      generate_kwargs={"language": "russian", "task": "transcribe"})
        return result["text"]

    return recognize


def filler_counts(reference, hypothesis, only=None):
    """(заполнителей в эталоне, из них найдено в ответе, заполнителей в ответе). only ограничивает набор заполнителей."""
    ref, hyp = find_fillers(reference), find_fillers(hypothesis)
    if only is not None:
        ref, hyp = [w for w in ref if w in only], [w for w in hyp if w in only]
    matched = 0
    remaining = list(hyp)
    for word in ref:
        if word in remaining:
            remaining.remove(word)
            matched += 1
    return len(ref), matched, len(hyp)


def evaluate(recognize, items):
    import jiwer

    references, hypotheses = [], []
    audio_seconds = 0.0
    ref_fillers = matched_fillers = hyp_fillers = 0
    ref_sounds = matched_sounds = 0
    count_errors = []
    started = time.time()
    for samples, reference in items:
        hypothesis = normalize_text(recognize(samples), keep_hyphens=True)
        references.append(for_wer(reference))
        hypotheses.append(for_wer(hypothesis))
        audio_seconds += len(samples) / SAMPLE_RATE
        r, m, h = filler_counts(reference, hypothesis)
        ref_fillers, matched_fillers, hyp_fillers = ref_fillers + r, matched_fillers + m, hyp_fillers + h
        r, m, _ = filler_counts(reference, hypothesis, only=SOUNDS)
        ref_sounds, matched_sounds = ref_sounds + r, matched_sounds + m
        n_ref = len(references[-1].split())
        count_errors.append(abs(len(hypotheses[-1].split()) - n_ref) / n_ref)
    elapsed = time.time() - started
    return {
        "n": len(items),
        "wer": round(jiwer.wer(references, hypotheses), 4),
        "word_count_error": round(float(np.mean(count_errors)), 4),
        "filler_recall": round(matched_fillers / ref_fillers, 4) if ref_fillers else None,
        "filler_precision": round(matched_fillers / hyp_fillers, 4) if hyp_fillers else None,
        "fillers_in_reference": ref_fillers,
        "sound_recall": round(matched_sounds / ref_sounds, 4) if ref_sounds else None,
        "sounds_in_reference": ref_sounds,
        "rtf": round(elapsed / audio_seconds, 4),
        "audio_minutes": round(audio_seconds / 60, 1),
    }, list(zip(references, hypotheses))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--datasets", nargs="+", default=list(DATASETS))
    parser.add_argument("--out", default="data/asr_benchmark.json")
    args = parser.parse_args(argv)

    out = Path(args.out)
    results = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    data = {name: load_dataset(name) for name in args.datasets}
    for model_name in args.models:
        recognize = make_model(model_name)
        recognize(np.zeros(SAMPLE_RATE, dtype=np.float32))  # прогрев, чтобы загрузка модели не попала в замер скорости
        results.setdefault(model_name, {})
        for name, items in data.items():
            metrics, pairs = evaluate(recognize, items)
            results[model_name][name] = metrics
            print(f"{model_name:32s} {name:9s} WER {metrics['wer']:.4f}  слова ±{metrics['word_count_error']:.3f}  "
                  f"заполнители: полнота {metrics['filler_recall']} точность {metrics['filler_precision']}  звуки-паузы {metrics['sound_recall']}  RTF {metrics['rtf']:.3f}", flush=True)
            Path("data/asr_samples").mkdir(exist_ok=True)
            Path(f"data/asr_samples/{model_name.replace('/', '_').replace(':', '_')}_{name}.json").write_text(
                json.dumps(pairs[:40], ensure_ascii=False, indent=1), encoding="utf-8")
        out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
