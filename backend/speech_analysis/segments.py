"""Разбивка расшифровки на фразы с оценкой каждой: темп, эмоциональная окраска, слова-заполнители.

Общие цифры по записи говорят, что темп высокий. Разметка по фразам показывает, где именно.
"""
import re

from .clarity import UNCLEAR_WORD_PROBABILITY, clarity_score, classify_clarity
from .fillers import split_by_fillers
from .speed import WORD_RE, classify_rate, spoken_length

MIN_SEGMENT_SEC = 3.0     # короче этого темп и эмоция считаются ненадёжно, фразы склеиваются
MIN_SEGMENT_WORDS = 4
MAX_SEGMENT_SEC = 15.0    # длиннее этого фраза режется, иначе «где именно» теряет смысл
MIN_EMOTION_SEC = 2.0
PAUSE_SEC = 0.9           # граница фразы для текста без пунктуации
SENTENCE_END = re.compile(r"[.!?…]")


def _words(tokens):
    """Текст, слова с временем начала [(начало в тексте, конец в тексте, секунда)] и вероятность для каждого символа."""
    text = "".join(token[0] for token in tokens)
    char_times, char_probs = [], []
    for token in tokens:
        piece, time = token[0], token[1]
        probability = token[2] if len(token) > 2 else None
        char_times.extend([time] * len(piece))
        char_probs.extend([probability] * len(piece))
    return text, [(m.start(), m.end(), char_times[m.start()]) for m in WORD_RE.finditer(text)], char_probs


def _sentence_groups(text, words):
    """Группы слов по предложениям. Если модель не ставит пунктуацию, границей служит пауза."""
    punctuated = SENTENCE_END.search(text) is not None
    groups, current = [], []
    for index, word in enumerate(words):
        current.append(index)
        if index + 1 == len(words):
            break
        between = text[word[1]:words[index + 1][0]]
        pause = words[index + 1][2] - word[2]
        if (SENTENCE_END.search(between) if punctuated else pause >= PAUSE_SEC):
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def _merge_short(groups, words, duration):
    def span(group, following):
        end = words[following[0]][2] if following else duration
        return end - words[group[0]][2]

    merged = []
    for group in groups:
        if merged and (len(merged[-1]) < MIN_SEGMENT_WORDS or words[group[0]][2] - words[merged[-1][0]][2] < MIN_SEGMENT_SEC):
            merged[-1] = merged[-1] + group
        else:
            merged.append(list(group))
    # Короткий хвост присоединяется к предыдущей фразе.
    if len(merged) > 1 and (len(merged[-1]) < MIN_SEGMENT_WORDS or span(merged[-1], None) < MIN_SEGMENT_SEC):
        tail = merged.pop()
        merged[-1] = merged[-1] + tail
    return merged


def _split_long(groups, words):
    result = []
    for group in groups:
        current = [group[0]]
        for index in group[1:]:
            if words[index][2] - words[current[0]][2] >= MAX_SEGMENT_SEC and len(group) - group.index(index) >= MIN_SEGMENT_WORDS:
                result.append(current)
                current = []
            current.append(index)
        result.append(current)
    return result


def build_segments(tokens, duration, thresholds, samples=None, sample_rate=16000, emotion=None):
    """Фразы расшифровки с оценками.

    tokens: [(кусочек текста, секунда начала)] или [(кусочек, секунда, вероятность)] от распознавателя.
    emotion: функция «отсчёты -> метка эмоции или None»; без неё окраска фраз не определяется.
    """
    text, words, char_probs = _words(tokens)
    if not words:
        return []
    groups = _split_long(_merge_short(_sentence_groups(text, words), words, duration), words)

    segments = []
    for number, group in enumerate(groups):
        first, last = words[group[0]], words[group[-1]]
        following = groups[number + 1] if number + 1 < len(groups) else None
        start = max(0.0, first[2])
        # Конец фразы: начало следующей. Пауза после фразы входит в неё, как и в общем темпе по записи.
        end = words[following[0]][2] if following else min(duration, max(last[2] + 0.6, start + 0.6))
        end = max(end, start + 0.3)
        text_end = words[following[0]][0] if following else len(text)
        raw = text[first[0]:text_end]
        piece = raw.strip()
        # Чёткость фразы и неразборчивые слова: по вероятностям кусочков, из которых модель собрала текст.
        probabilities = char_probs[first[0]:first[0] + len(piece)]
        score = clarity_score(probabilities)
        unclear = []
        for i in group:
            word_probs = [p for p in char_probs[words[i][0]:words[i][1]] if p is not None]
            if word_probs and min(word_probs) < UNCLEAR_WORD_PROBABILITY:
                unclear.append((words[i][0] - first[0], words[i][1] - first[0]))
        spoken = sum(spoken_length(text[words[i][0]:words[i][1]]) for i in group)
        rate = spoken / ((end - start) / 60.0)
        label = None
        if emotion is not None and samples is not None and end - start >= MIN_EMOTION_SEC:
            label = emotion(samples[int(start * sample_rate):int(end * sample_rate)])
        segments.append({
            "start": round(start, 2),
            "end": round(end, 2),
            "text": piece,
            "rate": round(rate),
            "rate_status": classify_rate(rate, thresholds),
            "emotion": label,
            "clarity": None if score is None else round(score),
            "clarity_level": classify_clarity(score, thresholds),
            "parts": split_by_fillers(piece, unclear),
        })
    return segments
