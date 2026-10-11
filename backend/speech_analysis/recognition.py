"""Распознавание речи собственными силами, без внешних сервисов.

Основная модель: GigaAM-v3 с Hugging Face в формате ONNX. Она выбрана замером на русской речи
(training/asr_benchmark.py, результаты в docs/MODELS.md). Запасной вариант: лёгкая модель Vosk.
Для автотестов есть заглушка с заранее заданным текстом.
"""
import json
import logging
import os

import numpy as np

from . import lang
from .audio import SAMPLE_RATE, speech_intervals, to_pcm16

log = logging.getLogger(__name__)


class RecognitionError(RuntimeError):
    """Сервис распознавания недоступен или вернул ошибку."""


def split_with_offsets(samples, max_sec=25.0):
    """Режет запись на куски не длиннее max_sec, стараясь резать по паузам. Возвращает [(смещение в отсчётах, кусок)]."""
    limit = int(max_sec * SAMPLE_RATE)
    if len(samples) <= limit:
        return [(0, samples)]
    bounds = []
    start = 0
    last_end = 0
    for _, end in speech_intervals(samples):
        end = int(end)
        if end - start > limit:
            if last_end > start:
                bounds.append((start, last_end))
                start = last_end
            while end - start > limit:  # одна фраза длиннее лимита: режем жёстко
                bounds.append((start, start + limit))
                start += limit
        last_end = end
    while len(samples) - start > limit:
        bounds.append((start, start + limit))
        start += limit
    if start < len(samples):
        bounds.append((start, len(samples)))
    return [(a, samples[a:b]) for a, b in bounds if b > a]


def split_for_recognition(samples, max_sec=25.0):
    return [chunk for _, chunk in split_with_offsets(samples, max_sec)]


def spread_evenly(text, duration):
    """Время слов для распознавателя, который его не сообщает: слова раскладываются по записи равномерно."""
    words = (text or "").split()
    if not words:
        return []
    step = duration / len(words)
    return [((" " if i else "") + word, i * step) for i, word in enumerate(words)]


class OnnxRecognizer:
    """Открытая модель распознавания в формате ONNX (пакет onnx-asr). Работает на процессоре, без PyTorch.

    Запись режется на куски до 25 секунд по паузам: акустические модели этого класса рассчитаны на короткие фразы.
    """

    name = "onnx"
    _models = {}

    def __init__(self, model_name, chunk_sec=25.0, quantization=None):
        self.model_name = model_name
        self.chunk_sec = chunk_sec
        key = model_name if quantization is None else f"{model_name}:{quantization}"
        if key not in self._models:
            try:
                import onnx_asr
            except ImportError as exc:
                raise RecognitionError("Пакет onnx-asr не установлен") from exc
            try:
                # Только процессор: ускоритель CoreML на macOS падает на части моделей, а сервер всё равно работает на Linux.
                self._models[key] = onnx_asr.load_model(model_name, quantization=quantization, providers=["CPUExecutionProvider"])
            except Exception as exc:
                raise RecognitionError(f"Не удалось загрузить модель распознавания {model_name}") from exc
        self.model = self._models[key]
        self._timed = None

    def recognize(self, samples):
        return "".join(piece for piece, _ in self.recognize_timed(samples)).strip()

    def recognize_timed(self, samples):
        """Текст по кусочкам с временем начала каждого: [(кусочек текста, секунда)]. Склейка кусочков даёт текст."""
        return [(piece, time) for piece, time, _ in self.recognize_detailed(samples)]

    def recognize_detailed(self, samples):
        """То же с вероятностью, с которой модель узнала кусочек: [(кусочек, секунда, вероятность или None)]."""
        if self._timed is None:
            self._timed = self.model.with_timestamps()
        tokens = []
        for offset, chunk in split_with_offsets(samples, max_sec=self.chunk_sec):
            if len(chunk) < SAMPLE_RATE // 10:
                continue
            try:
                result = self._timed.recognize(np.ascontiguousarray(chunk, dtype=np.float32), sample_rate=SAMPLE_RATE)
            except Exception as exc:
                raise RecognitionError("Сбой модели распознавания") from exc
            pieces = list(zip(result.tokens or [], result.timestamps or []))
            logprobs = getattr(result, "logprobs", None)
            if pieces and logprobs is not None and len(logprobs) == len(pieces):
                probabilities = [float(np.exp(value)) for value in logprobs]
            else:
                probabilities = [None] * len(pieces)
            if not pieces and (result.text or "").strip():
                pieces = spread_evenly(result.text.strip(), len(chunk) / SAMPLE_RATE)
                probabilities = [None] * len(pieces)
            if not pieces:
                continue
            base = offset / SAMPLE_RATE
            if tokens and not pieces[0][0].startswith(" "):
                tokens.append((" ", base + pieces[0][1], None))
            tokens.extend((piece, base + float(time), probability) for (piece, time), probability in zip(pieces, probabilities))
        return tokens


class BilingualRecognizer:
    """Русская и английская речь. Язык определяется по началу записи многоязычной моделью, затем запись целиком
    распознаёт модель этого языка: русскую речь лучше понимает GigaAM, английскую она не знает вовсе."""

    name = "bilingual"
    PROBE_SECONDS = 30

    def __init__(self, russian, english_factory):
        self.russian = russian
        self._english_factory = english_factory
        self._english = None

    def english(self):
        if self._english is None and self._english_factory is not None:
            try:
                self._english = self._english_factory()
            except RecognitionError:
                log.exception("Модель английской речи недоступна, записи разбираются как русские")
                self._english_factory = None
        return self._english

    def recognize(self, samples):
        return "".join(token[0] for token in self.recognize_detailed(samples)).strip()

    def recognize_detailed(self, samples):
        return self.recognize_bilingual(samples)[0]

    def recognize_bilingual(self, samples, language=None, fallback="ru"):
        """Возвращает (кусочки текста со временем и вероятностью, язык речи)."""
        english = self.english()
        if english is None:
            return self.russian.recognize_detailed(samples), "ru"
        if language not in ("ru", "en"):
            limit = self.PROBE_SECONDS * SAMPLE_RATE
            probe = english.recognize_detailed(samples[:limit])
            language = lang.detect("".join(token[0] for token in probe)) or fallback
            if language == "en" and len(samples) <= limit:
                return probe, "en"
        if language == "en":
            return english.recognize_detailed(samples), "en"
        return self.russian.recognize_detailed(samples), "ru"


class VoskRecognizer:
    """Офлайн-распознавание. Нужны пакет vosk и распакованная русская модель."""

    name = "vosk"
    _models = {}

    def __init__(self, model_path):
        if not os.path.isdir(model_path):
            raise RecognitionError(f"Модель Vosk не найдена: {model_path}")
        try:
            import vosk
        except ImportError as exc:
            raise RecognitionError("Пакет vosk не установлен") from exc
        vosk.SetLogLevel(-1)
        if model_path not in self._models:
            self._models[model_path] = vosk.Model(model_path)
        self._vosk = vosk
        self.model = self._models[model_path]

    def recognize(self, samples):
        return "".join(piece for piece, _ in self.recognize_timed(samples)).strip()

    def recognize_timed(self, samples):
        return [(piece, time) for piece, time, _ in self.recognize_detailed(samples)]

    def recognize_detailed(self, samples):
        recognizer = self._vosk.KaldiRecognizer(self.model, SAMPLE_RATE)
        recognizer.SetWords(True)
        pcm = to_pcm16(samples)
        words = []
        step = SAMPLE_RATE * 2 // 2  # полсекунды
        for offset in range(0, len(pcm), step):
            if recognizer.AcceptWaveform(pcm[offset:offset + step]):
                words.extend(json.loads(recognizer.Result()).get("result", []))
        words.extend(json.loads(recognizer.FinalResult()).get("result", []))
        return [((" " if i else "") + w["word"], float(w["start"]), w.get("conf")) for i, w in enumerate(words)]


class StubRecognizer:
    """Возвращает заранее заданный текст. Используется в тестах."""

    name = "stub"

    def __init__(self, text=""):
        self.text = text

    def recognize(self, samples):
        return self.text


def with_english(russian, config):
    """Добавляет к русской модели английскую, если она задана в настройках."""
    model = getattr(config, "ASR_MODEL_EN", "")
    if not model or model == "off":
        return russian
    quantization = getattr(config, "ASR_EN_QUANTIZATION", "") or None
    return BilingualRecognizer(russian, lambda: OnnxRecognizer(model, quantization=quantization))


def make_recognizer(config):
    kind = (config.RECOGNIZER or "auto").lower()
    if kind == "stub":
        return StubRecognizer(os.environ.get("STUB_TEXT", ""))
    if kind == "onnx":
        return with_english(OnnxRecognizer(config.ASR_MODEL), config)
    if kind == "vosk":
        return VoskRecognizer(config.VOSK_MODEL_PATH)
    if kind == "auto":
        try:
            return with_english(OnnxRecognizer(config.ASR_MODEL), config)
        except RecognitionError as primary:
            try:
                return VoskRecognizer(config.VOSK_MODEL_PATH)
            except RecognitionError:
                raise RecognitionError(
                    f"Распознавание речи не настроено: {primary}. Установите пакет onnx-asr или модель Vosk"
                ) from primary
    raise RecognitionError(f"Неизвестный распознаватель: {kind}")
