"""Дообученная «голова» для модели эмоций.

Кодировщик WavLM из Aniemore остаётся замороженным. Поверх него обучается небольшой
классификатор, который берёт взвешенную сумму всех слоёв кодировщика, а не только последнего.
Веса головы занимают около мегабайта и лежат в репозитории рядом с кодом.
"""
import numpy as np

from .audio import SAMPLE_RATE

EMOTIONS = ["anger", "disgust", "enthusiasm", "fear", "happiness", "neutral", "sadness"]


def pick_device():
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def load_encoder(model_id, device=None):
    from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

    model = AutoModelForAudioClassification.from_pretrained(model_id)
    extractor = AutoFeatureExtractor.from_pretrained(model_id)
    model.eval().to(device or pick_device())
    return model, extractor


def encode(model, extractor, clips):
    """Прогоняет записи через кодировщик.

    Возвращает (признаки [B, слои, 2 * размер], логиты исходной модели [B, классы]).
    Признак слоя: среднее и стандартное отклонение по времени. Среднее описывает общий тон записи,
    отклонение показывает, насколько он меняется. Маска исключает дополнение тишиной.
    """
    import torch

    device = next(model.parameters()).device
    inputs = extractor(clips, sampling_rate=SAMPLE_RATE, return_tensors="pt", padding=True, return_attention_mask=True)
    values = inputs["input_values"].to(device)
    mask = inputs["attention_mask"].to(device)
    with torch.inference_mode():
        out = model.wavlm(values, attention_mask=mask, output_hidden_states=True)
        frames = model._get_feature_vector_attention_mask(out.last_hidden_state.shape[1], mask)
        weight = frames.unsqueeze(-1).to(out.last_hidden_state.dtype)
        count = weight.sum(1).clamp(min=1)
        pooled = []
        for hidden in out.hidden_states:
            mean = (hidden * weight).sum(1) / count
            variance = (((hidden - mean.unsqueeze(1)) ** 2) * weight).sum(1) / count
            pooled.append(torch.cat([mean, variance.clamp(min=1e-8).sqrt()], dim=-1))
        layers = torch.stack(pooled, dim=1)
        projected = model.projector(out.last_hidden_state)
        logits = model.classifier((projected * weight).sum(1) / count)
    return layers.float().cpu().numpy(), logits.float().cpu().numpy()


def build_head(n_layers, dim, hidden, n_classes, dropout, layer_start=0):
    """Голова поверх признаков кодировщика.

    layer_start задаёт, с какого слоя брать признаки: 0 означает все слои, последний индекс
    оставляет только верхний слой. dim задаёт, сколько чисел брать из признака слоя: первая половина
    содержит средние, вторая отклонения. hidden=0 даёт линейный классификатор.
    """
    import torch
    from torch import nn

    class EmotionHead(nn.Module):
        def __init__(self):
            super().__init__()
            self.layer_start = layer_start
            self.layer_logits = nn.Parameter(torch.zeros(n_layers))
            self.register_buffer("mean", torch.zeros(n_layers, dim))
            self.register_buffer("std", torch.ones(n_layers, dim))
            if hidden:
                self.net = nn.Sequential(
                    nn.Dropout(dropout), nn.Linear(dim, hidden), nn.GELU(), nn.Dropout(dropout), nn.Linear(hidden, n_classes)
                )
            else:
                self.net = nn.Sequential(nn.Dropout(dropout), nn.Linear(dim, n_classes))

        def layer_weights(self):
            return torch.softmax(self.layer_logits, dim=0)

        def normalize(self, features):
            return (features[:, self.layer_start:, :dim] - self.mean) / self.std

        def pool(self, normalized):
            """Взвешенная сумма слоёв. Вход уже нормирован."""
            return torch.einsum("bld,l->bd", normalized, self.layer_weights())

        def forward(self, features):
            return self.net(self.pool(self.normalize(features)))

    return EmotionHead()


def save_head(head, path, config, meta):
    import torch

    torch.save({"config": config, "state": head.state_dict(), "meta": meta}, path)


def load_head(path, device="cpu"):
    import torch

    blob = torch.load(path, map_location=device, weights_only=True)
    head = build_head(**blob["config"])
    head.load_state_dict(blob["state"])
    head.eval().to(device)
    return head, blob["meta"]


def softmax(logits):
    shifted = logits - logits.max(axis=-1, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=-1, keepdims=True)


NEGATIVE = ("anger", "disgust", "fear", "sadness")


def decide(probabilities, negative_threshold=0.0):
    """Выбор класса по вероятностям записи. Возвращает номер класса.

    На отрицательную эмоцию приложение выдаёт совет «следить за настроением речи», поэтому ложная
    тревога стоит дороже пропуска. Отрицательный класс выбирается, только если модель уверена в нём
    не меньше порога; иначе берётся самый вероятный из остальных.
    """
    best = int(np.argmax(probabilities))
    if negative_threshold and EMOTIONS[best] in NEGATIVE and probabilities[best] < negative_threshold:
        calm = [i for i, name in enumerate(EMOTIONS) if name not in NEGATIVE]
        best = calm[int(np.argmax(probabilities[calm]))]
    return best
