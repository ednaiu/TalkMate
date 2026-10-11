"""Эмоциональная окраска речи.

Шаги со слайда: ресемплинг (при загрузке файла), нормализация амплитуды, сегментация на окна,
извлечение признаков кодировщиком WavLM, классификация.

Удаление шума по умолчанию выключено. Замер на тестовых выборках показал, что спектральное
вычитание снижает точность модели: на RESD с 0,811 до 0,793, на Dusha с 0,165 до 0,136.
Модель училась на необработанном звуке, и артефакты шумоподавления для неё непривычнее самого шума.
Режим можно сменить переменной EMOTION_PREPROCESS (raw, norm, denoise).

Два варианта классификатора:
- talkmate: кодировщик Aniemore и голова, дообученная на Dusha и RESD (training/train_head.py);
- aniemore: исходная модель Aniemore/wavlm-emotion-russian-resd без изменений.
"""
import logging
from pathlib import Path

import numpy as np

from . import lang
from .audio import SAMPLE_RATE
from .emotion_head import EMOTIONS, decide, softmax
from .preprocess import PREPROCESS_MODES

log = logging.getLogger(__name__)

WINDOW_SEC = 8.0
MAX_WINDOWS = 12
ENCODE_BATCH = 4
DEFAULT_PREPROCESS = "norm"
DEFAULT_HEAD = Path(__file__).parent / "weights" / "emotion_head.pt"

__all__ = ["EMOTIONS", "AniemoreEmotion", "HeadEmotion", "StubEmotion", "detect_emotion", "make_emotion", "windows"]


def windows(samples, window_sec=WINDOW_SEC, max_windows=MAX_WINDOWS):
    """Окна фиксированной длины. На длинной записи берём равномерную выборку окон."""
    size = int(window_sec * SAMPLE_RATE)
    if len(samples) <= size:
        return [samples]
    starts = list(range(0, len(samples) - size // 2, size))
    if len(starts) > max_windows:
        picks = np.linspace(0, len(starts) - 1, max_windows).round().astype(int)
        starts = [starts[i] for i in picks]
    return [samples[s:s + size] for s in starts]


class _EncoderBackend:
    """Общая часть: загрузка кодировщика один раз на процесс и прогон записи по окнам."""

    _encoders = {}
    preprocess = DEFAULT_PREPROCESS
    negative_threshold = 0.0
    # Порог для английской речи: уверенность модели на ней распределена иначе. None означает общий порог.
    negative_threshold_en = None

    def __init__(self, model_id):
        self.model_id = model_id

    def _encoder(self):
        if self.model_id not in self._encoders:
            from .emotion_head import load_encoder

            self._encoders[self.model_id] = load_encoder(self.model_id)
        return self._encoders[self.model_id]

    def _encode(self, samples):
        from .emotion_head import encode

        model, extractor = self._encoder()
        pieces = windows(samples)
        features, logits = [], []
        for start in range(0, len(pieces), ENCODE_BATCH):
            layer_features, base_logits = encode(model, extractor, pieces[start:start + ENCODE_BATCH])
            features.append(layer_features)
            logits.append(base_logits)
        return np.concatenate(features), np.concatenate(logits)

    def window_probabilities(self, samples):
        raise NotImplementedError

    def probabilities(self, samples):
        """Вероятности классов по записи: среднее по окнам."""
        return self.window_probabilities(samples).mean(axis=0)

    def predict(self, samples):
        threshold = self.negative_threshold
        if lang.speech() == "en" and self.negative_threshold_en is not None:
            threshold = self.negative_threshold_en
        return EMOTIONS[decide(self.probabilities(samples), threshold)]


class AniemoreEmotion(_EncoderBackend):
    name = "aniemore"

    def window_probabilities(self, samples):
        _, logits = self._encode(samples)
        return softmax(logits.astype(np.float64))


class HeadEmotion(_EncoderBackend):
    name = "talkmate"
    _heads = {}

    def __init__(self, model_id, head_path=DEFAULT_HEAD):
        super().__init__(model_id)
        self.head_path = str(head_path)
        self.head, meta = self._load_head()
        if meta.get("labels") != EMOTIONS:
            raise ValueError("Голова обучена на другом наборе классов")
        self.preprocess = meta.get("preprocess", DEFAULT_PREPROCESS)
        self.negative_threshold = float(meta.get("negative_threshold", 0.0))
        if "negative_threshold_en" in meta:
            self.negative_threshold_en = float(meta["negative_threshold_en"])

    def _load_head(self):
        if self.head_path not in self._heads:
            from .emotion_head import load_head

            self._heads[self.head_path] = load_head(self.head_path)
        return self._heads[self.head_path]

    def window_probabilities(self, samples):
        import torch

        features, _ = self._encode(samples)
        with torch.no_grad():
            logits = self.head(torch.from_numpy(features.astype(np.float32)))
        return torch.softmax(logits, dim=1).numpy()


class StubEmotion:
    name = "stub"

    def __init__(self, label="neutral"):
        self.label = label

    def predict(self, samples):
        return self.label


def make_emotion(config):
    kind = (config.EMOTION_BACKEND or "off").lower()
    backend = None
    if kind == "talkmate":
        head_path = Path(getattr(config, "EMOTION_HEAD", "") or DEFAULT_HEAD)
        if head_path.exists():
            backend = HeadEmotion(config.EMOTION_MODEL, head_path)
        else:
            log.warning("Веса головы не найдены (%s), используется исходная модель Aniemore", head_path)
            backend = AniemoreEmotion(config.EMOTION_MODEL)
    elif kind == "aniemore":
        backend = AniemoreEmotion(config.EMOTION_MODEL)
    elif kind == "stub":
        return StubEmotion()
    override = getattr(config, "EMOTION_PREPROCESS", "")
    if backend is not None and override:
        if override not in PREPROCESS_MODES:
            raise ValueError(f"Неизвестный режим EMOTION_PREPROCESS: {override}")
        backend.preprocess = override
    return backend


def detect_emotion(backend, samples):
    """Возвращает метку эмоции или None, если модель выключена или не загрузилась."""
    if backend is None:
        return None
    prepare = PREPROCESS_MODES[getattr(backend, "preprocess", DEFAULT_PREPROCESS)]
    try:
        label = backend.predict(prepare(samples))
    except Exception:
        log.exception("Не удалось определить эмоцию")
        return None
    return label if label in EMOTIONS else None
