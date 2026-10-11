import re
from collections import Counter

from . import lang
from .speed import tokens_with_spans

# Словосочетания проверяются раньше одиночных слов, чтобы «как бы» не посчиталось дважды.
FILLER_PHRASES = [
    ("как", "бы"),
    ("это", "самое"),
    ("так", "сказать"),
    ("в", "общем"),
    ("в", "принципе"),
    ("на", "самом", "деле"),
    ("скажем", "так"),
    ("как", "говорится"),
    ("в", "общем-то"),
]
FILLER_WORDS = {
    "ну", "вот", "типа", "короче", "значит", "собственно", "блин", "слушай", "общем-то", "так-то",
}

# Звуки-паузы: «э-э», «эм», «м-м», «а-а», «хм». Модель распознавания пишет их по-разному
# («э-э», «ээ», «э э»), поэтому все варианты сводятся к одной записи.
HESITATIONS = (
    (re.compile(r"^(?:э+(?:-э+)*м*)$"), "э-э"),
    (re.compile(r"^(?:м{2,}|м+(?:-м+)+|х+м+|гм+)$"), "м-м"),
    (re.compile(r"^(?:а{2,}|а+(?:-а+)+)$"), "а-а"),
)
# Протянутый гласный: «и-и-и», «о-о», «ууу». Говорящий тянет звук, пока подбирает слово.
DRAWL = re.compile(r"^([иоуые])(?:(?:-\1)+|\1{2,})$")
# Заполнитель с протянутым концом: «ну-у», «вот-т».
STRETCHED = re.compile(r"^(.+?)(?:-[а-яё])+$")

# Слова, которые бывают и обычными, и вставными: «так вышло» и «Так. Начнём». Заполнителем такое слово
# считается, только когда оно выделено знаками препинания с обеих сторон (или стоит в начале фразы).
ISOLATED_FILLERS = {"так", "да", "итак", "просто", "ладно", "хорошо", "окей", "ок", "понимаете", "знаете", "смотрите"}

# Английская речь. Состав тот же: словосочетания, слова, которые вставными бывают всегда, и слова, которые
# считаются заполнителем только между знаками препинания («Well, …», «it is, like, simple»).
FILLER_PHRASES_EN = [
    ("you", "know"),
    ("i", "mean"),
    ("sort", "of"),
    ("kind", "of"),
    ("you", "see"),
    ("or", "something"),
    ("to", "be", "honest"),
]
FILLER_WORDS_EN = {"basically", "literally", "kinda", "sorta", "anyways"}
ISOLATED_FILLERS_EN = {"like", "so", "well", "right", "okay", "ok", "actually", "anyway", "now", "look", "listen", "yeah", "honestly"}
HESITATIONS_EN = (
    (re.compile(r"^(?:u+h*m+|e+r*m+|h+m+|m{2,})$"), "um"),
    (re.compile(r"^(?:u+h+|e+r+|a+h+)$"), "uh"),
)
PUNCTUATION = ",.!?…:;—–"


def hesitation(token):
    """Каноническая запись звука-паузы или None, если это обычное слово."""
    for pattern, label in lang.rule(HESITATIONS, HESITATIONS_EN):
        if pattern.match(token):
            return label
    if lang.speech() == "en":
        return None
    drawl = DRAWL.match(token)
    if drawl:
        return f"{drawl.group(1)}-{drawl.group(1)}"
    return None


def _isolated(text, start, end):
    """Стоит ли слово особняком: перед ним начало текста или знак препинания, после него знак препинания."""
    before = text[:start].rstrip()
    after = text[end:].lstrip()
    return (not before or before[-1] in PUNCTUATION) and bool(after) and after[0] in PUNCTUATION


def filler_spans(text):
    """Заполнители с их местом в тексте: [(начало, конец, запись заполнителя)] в порядке появления."""
    tokens = tokens_with_spans(text)
    words = [word for word, _, _ in tokens]
    phrases = lang.rule(FILLER_PHRASES, FILLER_PHRASES_EN)
    always = lang.rule(FILLER_WORDS, FILLER_WORDS_EN)
    isolated = lang.rule(ISOLATED_FILLERS, ISOLATED_FILLERS_EN)
    found = []
    previous_hesitation = None
    i = 0
    while i < len(tokens):
        sound = hesitation(words[i])
        if sound is not None and words[i] == "мм" and i > 0 and words[i - 1].isdigit():
            sound = None  # «5 мм» в распознанном тексте: миллиметры, а не пауза
        if sound is not None:
            if sound == previous_hesitation:
                # «э э э» подряд: одна пауза, а не три. Выделение растягивается на все повторы.
                start, _, label = found[-1]
                found[-1] = (start, tokens[i][2], label)
            else:
                found.append((tokens[i][1], tokens[i][2], sound))
            previous_hesitation = sound
            i += 1
            continue
        previous_hesitation = None
        for phrase in phrases:
            if tuple(words[i:i + len(phrase)]) == phrase:
                found.append((tokens[i][1], tokens[i + len(phrase) - 1][2], " ".join(phrase)))
                i += len(phrase)
                break
        else:
            word = words[i]
            stretched = STRETCHED.match(word)
            if stretched and stretched.group(1) in always:
                word = stretched.group(1)   # «ну-у» считается как «ну»
            if word in always or (word in isolated and _isolated(text, tokens[i][1], tokens[i][2])):
                found.append((tokens[i][1], tokens[i][2], word))
            i += 1
    return found


def find_fillers(text):
    """Возвращает список найденных заполнителей в порядке появления."""
    return [label for _, _, label in filler_spans(text)]


def split_by_fillers(text, unclear=()):
    """Режет текст на куски для подсветки. Склейка кусков даёт исходный текст.

    unclear: участки неразборчивых слов [(начало, конец)]. Кусок получает пометки filler и unclear;
    заполнитель важнее: если слово и заполнитель, и неразборчиво, оно помечается как заполнитель.
    """
    marks = [None] * len(text)
    for start, end in unclear:
        for i in range(max(0, start), min(len(text), end)):
            marks[i] = "unclear"
    for start, end, _ in filler_spans(text):
        for i in range(start, end):
            marks[i] = "filler"
    parts, position = [], 0
    for i in range(1, len(text) + 1):
        if i == len(text) or marks[i] != marks[position]:
            parts.append({"text": text[position:i], "filler": marks[position] == "filler", "unclear": marks[position] == "unclear"})
            position = i
    return parts


def count_fillers(text):
    return len(find_fillers(text))


def top_fillers(found, limit=5):
    return [word for word, _ in Counter(found).most_common(limit)]
