import re

WORD_RE = re.compile(r"[a-zа-яё0-9]+(?:-[a-zа-яё0-9]+)*", re.IGNORECASE)


def normalize(word):
    return word.lower().replace("ё", "е")


def tokenize(text):
    return [normalize(w) for w in WORD_RE.findall(text or "")]


def tokens_with_spans(text):
    """Слова текста с их местом в исходной строке: [(слово в нижнем регистре, начало, конец)]."""
    return [(normalize(m.group()), m.start(), m.end()) for m in WORD_RE.finditer(text or "")]


def spoken_length(token):
    """Сколько слов человек произнёс за этим токеном.

    Модель распознавания пишет числа цифрами: «22» в тексте одно слово, а сказано было два.
    """
    if not token.isdigit():
        return 1
    try:
        from num2words import num2words

        from . import lang

        return len(num2words(int(token), lang=lang.speech()).replace("-", " ").split())
    except Exception:
        return 1


def count_words(text):
    return sum(spoken_length(token) for token in tokenize(text))


def speech_rate(text, duration_sec):
    """Темп: число распознанных слов, делённое на длительность записи в минутах."""
    if duration_sec <= 0:
        return 0.0
    return count_words(text) / (duration_sec / 60.0)


def classify_rate(rate, thresholds):
    if rate < thresholds["rate_slow"]:
        return "slow"
    if rate > thresholds["rate_fast"]:
        return "fast"
    return "normal"
