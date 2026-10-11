"""Разметка записи доклада: когда на экране сменился слайд.

Берёт видео, где слайды показаны на весь кадр, и находит моменты смены по разнице соседних кадров
(по кадру в секунду, окно с лицом докладчика закрыто маской). Одинаковые кадры склеиваются в один слайд,
поэтому возврат к прежнему слайду получает его же номер. Результат: список отрезков «с такой-то секунды
слайд такой-то», обзорный лист для проверки глазами и PDF из кадров слайдов.

Найденные границы нужно просмотреть и поправить руками: поле fixes в описании доклада сдвигает,
добавляет или убирает границу.
"""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

SMALL = (160, 90)


def frames(video, size=SMALL, fps=1):
    """Кадры в оттенках серого, по одному в секунду."""
    width, height = size
    raw = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(video), "-vf", f"fps={fps},scale={width}:{height},format=gray",
         "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, height, width).astype(np.float32)


def mask_for(rects, size=SMALL):
    """Маска кадра: False там, где окно с лицом. rects заданы долями кадра: [x0, y0, x1, y1]."""
    width, height = size
    mask = np.ones((height, width), dtype=bool)
    for x0, y0, x1, y1 in rects:
        mask[int(y0 * height):int(y1 * height), int(x0 * width):int(x1 * width)] = False
    return mask


def find_changes(stack, mask, threshold, min_seconds):
    """Секунды, на которых кадр заметно отличается от предыдущего. Близкие смены считаются одной."""
    diffs = [float(np.abs(stack[i] - stack[i - 1])[mask].mean()) for i in range(1, len(stack))]
    changes = []
    for second, diff in enumerate(diffs, start=1):
        if diff >= threshold:
            if changes and second - changes[-1] < min_seconds:
                changes[-1] = second       # анимация появления: границей считается её конец
            else:
                changes.append(second)
    return changes


def label_slides(stack, mask, bounds, same):
    """Номер слайда для каждого отрезка: отрезок с тем же кадром, что был раньше, получает прежний номер."""
    keys, labels = [], []
    for start, end in bounds:
        middle = stack[min(len(stack) - 1, (start + end) // 2)]
        for index, key in enumerate(keys):
            if float(np.abs(middle - key)[mask].mean()) < same:
                labels.append(index)
                break
        else:
            keys.append(middle)
            labels.append(len(keys) - 1)
    return labels


def annotate(video, rects, threshold=4.0, min_seconds=3, same=3.0, fixes=None):
    stack = frames(video)
    mask = mask_for(rects)
    changes = find_changes(stack, mask, threshold, min_seconds)
    fixes = fixes or {}
    changes = sorted((set(changes) - set(fixes.get("remove", []))) | set(fixes.get("add", [])))
    edges = [0] + changes + [len(stack)]
    bounds = [(edges[i], edges[i + 1]) for i in range(len(edges) - 1) if edges[i + 1] > edges[i]]
    labels = label_slides(stack, mask, bounds, same)
    return [{"start": start, "end": end, "slide": label + 1} for (start, end), label in zip(bounds, labels)]


def grab(video, second, width=1280):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(second), "-i", str(video), "-frames:v", "1",
                          "-vf", f"scale={width}:-2", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, check=True).stdout
    import io

    return Image.open(io.BytesIO(raw)).convert("RGB")


def export(video, spans, rects, folder, name):
    """PDF из кадров слайдов (окно с лицом закрашено) и обзорный лист отрезков."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    first = {}
    for span in spans:
        first.setdefault(span["slide"], span)
    pages = []
    for slide in sorted(first):
        span = first[slide]
        image = grab(video, (span["start"] + span["end"]) / 2)
        for x0, y0, x1, y1 in rects:
            box = (int(x0 * image.width), int(y0 * image.height), int(x1 * image.width), int(y1 * image.height))
            image.paste((255, 255, 255), box)
        pages.append(image)
    pages[0].save(folder / f"{name}.pdf", save_all=True, append_images=pages[1:], resolution=96)
    thumbs = [grab(video, (s["start"] + s["end"]) / 2, width=320) for s in spans]
    columns = 5
    rows = (len(thumbs) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * 320, rows * thumbs[0].height), "white")
    for i, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((i % columns) * 320, (i // columns) * thumb.height))
    sheet.save(folder / f"{name}_spans.jpg", quality=80)
    return len(pages)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--talks", default="training/results/slide_alignment/talks.json")
    parser.add_argument("--videos", default="data/talks")
    args = parser.parse_args()
    talks = json.loads(Path(args.talks).read_text())
    for talk in talks:
        video = Path(args.videos) / f"{talk['id']}.mp4"
        spans = annotate(video, talk.get("mask", []), talk.get("threshold", 4.0), fixes=talk.get("fixes"))
        count = export(video, spans, talk.get("mask", []), args.videos, talk["id"])
        Path(args.talks).with_name(f"{talk['id']}.json").write_text(json.dumps({"id": talk["id"], "spans": spans}, ensure_ascii=False, indent=1))
        print(talk["id"], "слайдов", count, "отрезков", len(spans), [(s["start"], s["slide"]) for s in spans])
