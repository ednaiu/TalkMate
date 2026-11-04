"""Замер на своём тестовом наборе: настоящие репетиции пользователей с ручной дословной расшифровкой.

Открытые наборы (Podlodka, SOVA, FLEURS, Dusha) не похожи на запись репетиции с телефона. Этот скрипт
считает те же величины на своих записях, поэтому каждое изменение моделей проверяется на нём.

Формат набора, по умолчанию data/own_testset/:

    rec001.m4a          запись (любой формат, который читает приложение)
    rec001.txt          дословная расшифровка: все слова как сказаны, заполнители и звуки-паузы («э-э», «м-м»)
    rec001.json         необязательно, оценки людей: {"pace": "slow|ok|fast", "noisy": false, "emotion": "neutral"}

Черновик набора даёт training/export_dataset.py: записи людей, давших согласие, и расшифровка модели,
которую разметчик правит до дословной.

    python -m training.own_testset --data data/own_testset --out training/results/own_testset.json
"""
import argparse
import json
from pathlib import Path

from speech_analysis.audio import duration_seconds, load_audio
from speech_analysis.noise import classify_noise, estimate_snr_db
from speech_analysis.speed import speech_rate
from speech_analysis.thresholds import DEFAULT_THRESHOLDS

from .asr_benchmark import SOUNDS, filler_counts, for_wer, normalize_text

AUDIO = (".wav", ".m4a", ".mp3", ".ogg", ".flac", ".aac", ".3gp", ".webm")


def load_items(folder):
    """Записи с расшифровкой: (имя, путь к звуку, эталонный текст, оценки людей)."""
    items = []
    for text_path in sorted(Path(folder).glob("*.txt")):
        audio = next((text_path.with_suffix(ext) for ext in AUDIO if text_path.with_suffix(ext).exists()), None)
        if audio is None:
            continue
        labels_path = text_path.with_suffix(".json")
        labels = json.loads(labels_path.read_text(encoding="utf-8")) if labels_path.exists() else {}
        items.append((text_path.stem, audio, text_path.read_text(encoding="utf-8"), labels))
    return items


def pace_label(rate, thresholds):
    if rate > thresholds["rate_fast"]:
        return "fast"
    if 0 < rate < thresholds["rate_slow"]:
        return "slow"
    return "ok"


def _share(hits, total):
    return round(hits / total, 4) if total else None


def evaluate(items, recognize, thresholds=DEFAULT_THRESHOLDS):
    """Сводка и строки по записям. recognize: функция «отсчёты -> текст»."""
    import jiwer

    rows, references, hypotheses = [], [], []
    totals = {"fillers": 0, "fillers_found": 0, "fillers_said": 0, "sounds": 0, "sounds_found": 0}
    pace_hits = pace_total = noise_hits = noise_total = 0
    for name, path, raw_reference, labels in items:
        samples = load_audio(path)
        duration = duration_seconds(samples)
        reference = normalize_text(raw_reference, keep_hyphens=True)
        hypothesis = normalize_text(recognize(samples), keep_hyphens=True)
        references.append(for_wer(reference))
        hypotheses.append(for_wer(hypothesis))
        r, m, h = filler_counts(reference, hypothesis)
        totals["fillers"] += r
        totals["fillers_found"] += m
        totals["fillers_said"] += h
        r, m, _ = filler_counts(reference, hypothesis, only=SOUNDS)
        totals["sounds"] += r
        totals["sounds_found"] += m
        true_rate, model_rate = speech_rate(reference, duration), speech_rate(hypothesis, duration)
        snr = estimate_snr_db(samples)
        row = {"name": name, "seconds": round(duration, 1), "wer": round(jiwer.wer(references[-1], hypotheses[-1]), 4),
               "rate_reference": round(true_rate), "rate_model": round(model_rate), "snr_db": snr,
               "noise": classify_noise(snr, thresholds)}
        if "pace" in labels:
            pace_total += 1
            row["pace_people"] = labels["pace"]
            row["pace_app"] = pace_label(model_rate, thresholds)
            pace_hits += row["pace_app"] == labels["pace"]
        if "noisy" in labels and row["noise"] is not None:
            noise_total += 1
            noise_hits += (row["noise"] == "noisy") == bool(labels["noisy"])
        rows.append(row)
    summary = {
        "recordings": len(rows),
        "audio_minutes": round(sum(r["seconds"] for r in rows) / 60, 1),
        "wer": round(jiwer.wer(references, hypotheses), 4) if rows else None,
        "filler_recall": _share(totals["fillers_found"], totals["fillers"]),
        "filler_precision": _share(totals["fillers_found"], totals["fillers_said"]),
        "sound_recall": _share(totals["sounds_found"], totals["sounds"]),
        "sounds_in_reference": totals["sounds"],
        "pace_agreement_with_people": _share(pace_hits, pace_total),
        "noise_agreement_with_people": _share(noise_hits, noise_total),
        "mean_rate_error": round(sum(abs(r["rate_model"] - r["rate_reference"]) for r in rows) / len(rows), 1) if rows else None,
    }
    return summary, rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default="data/own_testset")
    parser.add_argument("--model", help="модель из training.asr_benchmark; по умолчанию та, что настроена в приложении")
    parser.add_argument("--out", default="training/results/own_testset.json")
    args = parser.parse_args(argv)

    items = load_items(args.data)
    if not items:
        raise SystemExit(f"В {args.data} нет пар «запись + .txt»")
    if args.model:
        from .asr_benchmark import make_model

        recognize = make_model(args.model)
    else:
        from speech_analysis.recognition import make_recognizer
        from talkmate.config import Config

        recognize = make_recognizer(Config()).recognize
    summary, rows = evaluate(items, recognize)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({"summary": summary, "recordings": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
