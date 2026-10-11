"""Точность привязки речи к слайдам на настоящих докладах.

Данные: записи докладов, где слайды показаны на весь кадр (training/results/slide_alignment/talks.json).
Эталон: отрезки «с такой-то секунды слайд такой-то», размеченные slide_frames.py по видео и проверенные глазами.
Речь распознаётся тем же распознавателем, что в приложении, слайды читаются из PDF, собранного из кадров.

Мера: доля времени речи, привязанного к верному слайду. Рядом для сравнения стоит привязка без всякого
анализа, когда слайды считаются показанными поровну.
"""
import argparse
import json
import pickle
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from speech_analysis.audio import SAMPLE_RATE, duration_seconds, load_audio  # noqa: E402
from speech_analysis.embeddings import TextEmbedder  # noqa: E402
from speech_analysis.recognition import make_recognizer  # noqa: E402
from speech_analysis.segments import build_segments  # noqa: E402
from speech_analysis.slide_match import align, lexical_similarity, match_slides, semantic_similarity  # noqa: E402
from speech_analysis.slides import SlideReader  # noqa: E402
from speech_analysis.thresholds import DEFAULT_THRESHOLDS  # noqa: E402


def prepare(talk, folder, recognizer, reader):
    """Фразы речи и слайды доклада. Распознавание и чтение слайдов сохраняются, чтобы не повторять их при подборе."""
    cache = folder / f"{talk}.pkl"
    if cache.exists():
        return pickle.loads(cache.read_bytes())
    wav = folder / f"{talk}.wav"
    if not wav.exists():
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(folder / f"{talk}.mp4"), "-ac", "1", "-ar", str(SAMPLE_RATE), str(wav)], check=True)
    samples = load_audio(wav)
    duration = duration_seconds(samples)
    tokens = recognizer.recognize_detailed(samples)
    segments = build_segments(tokens, duration, DEFAULT_THRESHOLDS, samples, SAMPLE_RATE)
    data = {"segments": segments, "duration": duration, "slides": reader.read(folder / f"{talk}.pdf")}
    cache.write_bytes(pickle.dumps(data))
    return data


def truth_for(segments, spans):
    """Верный слайд фразы: тот, что был на экране бо́льшую часть её времени."""
    labels = []
    for segment in segments:
        overlap = {}
        for span in spans:
            shared = min(segment["end"], span["end"]) - max(segment["start"], span["start"])
            if shared > 0:
                overlap[span["slide"]] = overlap.get(span["slide"], 0) + shared
        labels.append(max(overlap, key=overlap.get) - 1 if overlap else None)
    return labels


def score(predicted, truth, segments):
    """Доля времени речи на верном слайде и на верном либо соседнем."""
    exact = near = total = 0.0
    for guess, label, segment in zip(predicted, truth, segments):
        if label is None:
            continue
        length = segment["end"] - segment["start"]
        total += length
        exact += length * (guess == label)
        near += length * (abs(guess - label) <= 1)
    return exact / total, near / total


def marks(spans):
    return [{"page": span["slide"], "start": span["start"]} for span in spans]


def detection(prepared, truths, embedder):
    """Раскрытие слайда при точных отметках смены: как часто показанный слайд признан раскрытым и как часто
    раскрытым признан слайд, о котором не говорили (слайды одного доклада с речью другого)."""
    shown = found = wrong = foreign = 0
    keys = list(prepared)
    for number, key in enumerate(keys):
        data, spans = prepared[key], truths[key]
        report = match_slides(data["slides"], data["segments"], data["duration"], marks(spans), embedder)
        spoken = {label for label in truth_for(data["segments"], spans) if label is not None}
        for index, item in enumerate(report["items"]):
            if index in spoken and item["status"] != "no_text":
                shown += 1
                found += item["status"] != "skipped"
        other = prepared[keys[(number + 1) % len(keys)]]
        pages = len(other["slides"])
        moved = [{"page": (mark["page"] - 1) % pages + 1, "start": mark["start"]} for mark in marks(spans)]
        mixed = match_slides(other["slides"], data["segments"], data["duration"], moved, embedder)
        for item in mixed["items"]:
            if item["seconds"] > 0 and item["status"] != "no_text":
                foreign += 1
                wrong += item["status"] != "skipped"
    return {"показанных слайдов": shown, "из них признано раскрытыми": round(found / shown, 3),
            "чужих слайдов": foreign, "из них ошибочно признано раскрытыми": round(wrong / foreign, 3)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", default="data/talks")
    parser.add_argument("--results", default="training/results/slide_alignment")
    parser.add_argument("--models", nargs="*", default=["intfloat/multilingual-e5-small", "cointegrated/rubert-tiny2"])
    parser.add_argument("--weights", nargs="*", type=float, default=[0.1, 0.25, 0.5, 1.0])
    args = parser.parse_args()
    folder, results = Path(args.folder), Path(args.results)
    talks = json.loads((results / "talks.json").read_text())

    from talkmate.config import Config

    recognizer, reader = None, SlideReader()
    prepared = {}
    for talk in talks:
        if not (folder / f"{talk['id']}.pkl").exists() and recognizer is None:
            recognizer = make_recognizer(Config())
        prepared[talk["id"]] = prepare(talk["id"], folder, recognizer, reader)

    variants = {"поровну на слайд": lambda lex, sem: np.zeros_like(lex), "общие слова": lambda lex, sem: lex}
    semantics = {}
    for model in args.models:
        embedder = TextEmbedder(model)
        short = model.split("/")[-1]
        semantics[short] = {key: semantic_similarity(data["slides"], data["segments"], embedder) for key, data in prepared.items()}
        variants[f"смысл, {short}"] = None
        for weight in args.weights:
            variants[f"слова + смысл x{weight:g}, {short}"] = None

    table = {}
    for name in variants:
        rows = []
        for talk in talks:
            data = prepared[talk["id"]]
            spans = json.loads((results / f"{talk['id']}.json").read_text())["spans"]
            segments, slides, duration = data["segments"], data["slides"], data["duration"]
            lex = np.array(lexical_similarity(slides, segments))
            if name == "поровну на слайд":
                sim = np.zeros_like(lex)
            elif name == "общие слова":
                sim = lex
            else:
                short = name.split(", ")[-1]
                sem = semantics[short][talk["id"]]
                sim = sem if name.startswith("смысл") else lex + float(name.split("x")[1].split(",")[0]) * sem
            positions = [((s["start"] + s["end"]) / 2) / duration for s in segments]
            predicted = align(sim.tolist(), positions, len(slides))
            rows.append(score(predicted, truth_for(segments, spans), segments))
        minutes = [prepared[t["id"]]["duration"] for t in talks]
        mean = sum(r[0] * m for r, m in zip(rows, minutes)) / sum(minutes)
        near = sum(r[1] * m for r, m in zip(rows, minutes)) / sum(minutes)
        table[name] = {"по докладам": [round(r[0], 3) for r in rows], "точно": round(mean, 3), "с соседним": round(near, 3)}
        print(f"{name:48s} {' '.join(f'{r[0]:.2f}' for r in rows)}  | точно {mean:.3f}  с соседним {near:.3f}")
    truths = {t["id"]: json.loads((results / f"{t['id']}.json").read_text())["spans"] for t in talks}
    coverage = {"по словам": detection(prepared, truths, None)}
    for model in args.models[:1]:
        coverage[f"слова и смысл, {model.split('/')[-1]}"] = detection(prepared, truths, TextEmbedder(model))
    for name, row in coverage.items():
        print(name, row)
    summary = {
        "talks": [{"id": t["id"], "title": t["title"], "seconds": round(prepared[t["id"]]["duration"]),
                   "slides": len(prepared[t["id"]]["slides"]), "phrases": len(prepared[t["id"]]["segments"])} for t in talks],
        "variants": table,
        "coverage": coverage,
    }
    (results / "alignment.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
