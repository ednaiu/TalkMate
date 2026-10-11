"""Смысловые векторы фраз: по ним слайд узнаётся и тогда, когда докладчик пересказывает его своими словами."""
import logging

log = logging.getLogger(__name__)

MAX_TOKENS = 256


class TextEmbedder:
    """Модель-кодировщик с усреднением по словам. Загружается при первом обращении."""

    def __init__(self, model_id="intfloat/multilingual-e5-small"):
        self.model_id = model_id
        self._model = None
        self._tokenizer = None

    def _load(self):
        if self._model is None:
            from transformers import AutoModel, AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self.model_id)
            self._model = AutoModel.from_pretrained(self.model_id).eval()

    def encode(self, texts, kind="query"):
        """Единичные векторы текстов. kind: query для фраз речи, passage для слайдов (так обучены модели E5)."""
        import torch

        self._load()
        if "e5" in self.model_id.lower():
            texts = [f"{kind}: {text}" for text in texts]
        vectors = []
        with torch.no_grad():
            for start in range(0, len(texts), 16):
                batch = self._tokenizer(texts[start:start + 16], padding=True, truncation=True, max_length=MAX_TOKENS, return_tensors="pt")
                hidden = self._model(**batch).last_hidden_state
                mask = batch["attention_mask"].unsqueeze(-1).to(hidden.dtype)
                pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1)
                vectors.append(torch.nn.functional.normalize(pooled, dim=-1))
        return torch.cat(vectors).numpy() if vectors else None


class StubEmbedder:
    """Для тестов: вектор задаётся словарём «слово -> ось», синонимы попадают на одну ось."""

    def __init__(self, axes, size=8):
        self.axes = axes
        self.size = size

    def encode(self, texts, kind="query"):
        import numpy as np

        from .speed import tokenize

        out = np.zeros((len(texts), self.size), dtype="float32")
        for row, text in enumerate(texts):
            for word in tokenize(text):
                if word in self.axes:
                    out[row, self.axes[word]] += 1.0
            norm = np.linalg.norm(out[row])
            if norm:
                out[row] /= norm
        return out


def make_embedder(config):
    model = getattr(config, "SLIDES_EMBEDDER", "")
    if not model or model == "off":
        return None
    return TextEmbedder(model)
