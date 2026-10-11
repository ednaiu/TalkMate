"""Основная мысль выступления: пересказ локальной моделью.

Модель cointegrated/rut5-base-absum (244 млн параметров, около 900 МБ) работает на сервере, расшифровка
никуда не отправляется. Выбор цитаты по частоте слов (content.main_idea) остаётся запасным вариантом
на случай, если модель не установлена или не загрузилась.

Модель небольшая: на связном тексте она формулирует мысль, на сбивчивом может ограничиться его началом.
"""
import logging
import re

from .content import content_words, split_sentences, strip_fillers
from .speed import tokenize

log = logging.getLogger(__name__)

GREETING = re.compile(r"^(здравствуйте|добрый (день|вечер)|доброе утро|привет|приветствую)\b", re.IGNORECASE)
MIN_WORDS = 12          # на более коротком тексте пересказывать нечего
MAX_SUMMARY_WORDS = 40


def prepare(text):
    """Текст для модели: без слов-заполнителей и без вводных фраз в начале.

    Модель склонна повторять первое предложение. Если это приветствие или обрывок вроде «Проверка записи.»,
    пересказ получается пустым, поэтому такие фразы в начале отбрасываются.
    """
    sentences = [strip_fillers(s) for s in split_sentences(text)]
    sentences = [s for s in sentences if tokenize(s)]
    while len(sentences) > 2 and (GREETING.match(sentences[0]) or len(content_words(sentences[0])) < 3):
        sentences.pop(0)
    return " ".join(sentences)


def tidy(summary):
    summary = re.sub(r"\s+", " ", summary or "").strip()
    if not summary:
        return None
    summary = summary[0].upper() + summary[1:]
    return summary if summary[-1] in ".!?…" else summary + "."


class Rut5Summarizer:
    name = "rut5"
    _cache = {}

    def __init__(self, model_id="cointegrated/rut5-base-absum", target_words=15):
        self.model_id = model_id
        self.target_words = target_words

    def _load(self):
        if self.model_id not in self._cache:
            from transformers import T5ForConditionalGeneration, T5Tokenizer

            tokenizer = T5Tokenizer.from_pretrained(self.model_id)
            model = T5ForConditionalGeneration.from_pretrained(self.model_id).eval()
            self._cache[self.model_id] = (tokenizer, model)
        return self._cache[self.model_id]

    def summarize(self, text):
        """Пересказ в одну-две фразы или None, если текст слишком короткий либо результат непригоден."""
        source = prepare(text)
        if len(tokenize(source)) < MIN_WORDS:
            return None
        import torch

        tokenizer, model = self._load()
        # Число в квадратных скобках: подсказка модели о желаемой длине пересказа в словах.
        inputs = tokenizer(f"[{self.target_words}] {source}", return_tensors="pt", truncation=True, max_length=600)
        with torch.inference_mode():
            output = model.generate(**inputs, max_length=64, num_beams=4, repetition_penalty=10.0, no_repeat_ngram_size=3)
        summary = tidy(tokenizer.decode(output[0], skip_special_tokens=True))
        if summary is None or len(tokenize(summary)) > MAX_SUMMARY_WORDS or len(content_words(summary)) < 2:
            return None
        return summary


def make_summarizer(config):
    kind = (getattr(config, "MAIN_IDEA_BACKEND", "") or "rut5").lower()
    if kind == "rut5":
        return Rut5Summarizer(getattr(config, "MAIN_IDEA_MODEL", "") or "cointegrated/rut5-base-absum")
    return None


def summarize_safely(summarizer, text):
    """Пересказ или None: сбой модели не должен ронять разбор записи."""
    from . import lang

    # Модель пересказа обучена на русских текстах, на английских она выдаёт бессмыслицу.
    if lang.speech() != "ru":
        return None
    if summarizer is None:
        return None
    try:
        return summarizer.summarize(text)
    except Exception:
        log.exception("Не удалось получить пересказ, используется выбор цитаты")
        return None
