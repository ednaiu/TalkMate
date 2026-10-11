"""Сервер анализа речи: отдельный узел с диаграммы компонентов.

Принимает запись, возвращает показатели. Пороговые значения читает из той же базы,
что и сервер приложения, поэтому правки администратора действуют сразу.
"""
import json
import logging
import tempfile
from dataclasses import asdict
from pathlib import Path

from flask import Flask, jsonify, request
from sqlalchemy import Column, Float, MetaData, String, Table, create_engine, select

from .audio import AudioError
from .embeddings import make_embedder
from . import lang
from .emotion import make_emotion
from .pipeline import analyze
from .recognition import RecognitionError, make_recognizer
from .slides import make_slide_reader
from .summarizer import make_summarizer
from .thresholds import DEFAULT_THRESHOLDS

log = logging.getLogger(__name__)
MAX_SLIDE_MARKS = 1000
threshold_table = Table("threshold", MetaData(), Column("key", String(64), primary_key=True), Column("value", Float))


def read_thresholds(engine):
    values = dict(DEFAULT_THRESHOLDS)
    if engine is None:
        return values
    try:
        with engine.connect() as connection:
            for key, value in connection.execute(select(threshold_table.c.key, threshold_table.c.value)):
                if key in values:
                    values[key] = float(value)
    except Exception:
        log.exception("Не удалось прочитать пороги из базы, используются значения по умолчанию")
    return values


def parse_slide_times(raw):
    """Отметки приложения о смене слайдов: [{"page": 2, "start": 14.2}]. Непонятные данные отбрасываются целиком."""
    if not raw:
        return None
    try:
        marks = [{"page": int(item["page"]), "start": float(item["start"])} for item in json.loads(raw)]
    except (ValueError, TypeError, KeyError):
        return None
    if not marks or len(marks) > MAX_SLIDE_MARKS or any(m["page"] < 1 or m["start"] < 0 for m in marks):
        return None
    return marks


def create_analysis_app(config=None, recognizer=None, emotion_backend=None, engine=None):
    if config is None:
        from talkmate.config import Config

        config = Config()
    app = Flask(__name__)
    app.json.ensure_ascii = False
    app.config["MAX_CONTENT_LENGTH"] = (config.MAX_AUDIO_MB + config.MAX_SLIDES_MB) * 1024 * 1024
    if engine is None and config.DATABASE_URL:
        engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)
    state = {"recognizer": recognizer, "emotion": emotion_backend, "emotion_ready": emotion_backend is not None,
             "summarizer": make_summarizer(config), "slides": make_slide_reader(config),
             "embedder": make_embedder(config)}

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.post("/analyze")
    def analyze_audio():
        if config.ANALYSIS_TOKEN and request.headers.get("X-Analysis-Token") != config.ANALYSIS_TOKEN:
            return jsonify({"error": "forbidden", "message": "Неверный токен сервера анализа"}), 403
        upload = request.files.get("audio")
        if upload is None or not upload.filename:
            return jsonify({"error": "no_audio", "message": "Не передан аудиофайл"}), 400
        suffix = Path(upload.filename).suffix or ".wav"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / f"audio{suffix}"
            upload.save(path)
            slides_path = None
            slides = request.files.get("slides")
            if slides is not None and slides.filename:
                slides_path = Path(folder) / "slides.pdf"
                slides.save(slides_path)
            try:
                if state["recognizer"] is None:
                    state["recognizer"] = make_recognizer(config)
                if not state["emotion_ready"]:
                    state["emotion"] = make_emotion(config)
                    state["emotion_ready"] = True
                result = analyze(path, read_thresholds(engine), state["recognizer"], state["emotion"], state["summarizer"],
                                 slides_path, state["slides"], parse_slide_times(request.form.get("slide_times")),
                                 state["embedder"], request.form.get("speech_lang"),
                                 lang.normalize(request.form.get("ui_lang")))
            except AudioError as exc:
                return jsonify({"error": "bad_audio", "message": str(exc)}), 422
            except RecognitionError as exc:
                log.error("Распознавание не удалось: %s", exc)
                return jsonify({"error": "recognition_unavailable", "message": str(exc)}), 503
        return jsonify(asdict(result))

    return app
