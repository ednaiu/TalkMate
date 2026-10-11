"""Сопоставление речи со слайдами презентации.

Что это даёт выступающему:
- какие слайды он раскрыл словами, а какие показал молча или проскочил;
- сколько времени ушло на каждый слайд;
- где он читал текст со слайда вместо рассказа;
- какие слайды перегружены текстом или набраны мелко.

Метод. Слайд и фраза речи превращаются в наборы основ значимых слов. Слово тем весомее, чем на меньшем
числе слайдов оно встречается (обратная документная частота): название проекта есть на каждом слайде и
ничего не говорит о том, какой из них сейчас на экране. Фразы привязываются к слайдам динамическим
программированием при одном ограничении: слайды идут по порядку, назад докладчик не возвращается. Там, где
общих слов нет, решение принимает слабое предположение о равномерном темпе показа.

Если подключён кодировщик смысловых векторов (embeddings.py), он участвует дважды: добавляет к сходству по
словам сходство по смыслу и отличает слайд, пересказанный своими словами, от слайда, о котором промолчали.
Если приложение прислало отметки о смене слайдов, привязка берётся из них, и время на слайд точное.

Ограничения. Латинские надписи на слайде с русской речью не сверяются: распознаватель записал бы их
кириллицей. Без отметок приложения время на слайд оценивается по словам и на слайдах без текста
приблизительно. Возврат к прежнему слайду без отметок не виден.
"""
import logging
import math
import re
from collections import Counter

from . import lang
from .content import content_words, stem
from .speed import tokenize

log = logging.getLogger(__name__)

CYRILLIC = re.compile("[а-яё]")
KEY_TERMS = 10            # столько самых весомых слов слайда проверяется в речи
DENSE_WORDS = 45          # больше слов зритель не успевает прочитать, пока слушает
READING_NGRAM = 4         # четыре слова подряд, совпавшие со слайдом, считаются прочитанными
READING_SHARE = 50        # процент прочитанных слов, после которого слайд считается зачитанным
SMALL_TEXT_SHARE = 0.5
MAX_LISTED = 6            # в замечании перечисляется не больше стольких слайдов
UNRELATED = 10            # общий процент раскрытия, ниже которого речь и презентация считаются разными
SKIPPED_BELOW = 15        # процент раскрытия, ниже которого слайд считается нераскрытым
MEANING_WEIGHT = 0.25     # вес сходства по смыслу в привязке относительно сходства по словам
# Средний косинус фраз со слайдом, с которого слайд без общих слов считается пересказанным. Подобран для
# multilingual-e5-small: у показанных слайдов он почти всегда выше 0,83, у чужих почти всегда ниже.
RETOLD_MEANING = 0.83
PRIOR = 0.6               # вес предположения о равномерном темпе относительно одного совпавшего слова


def slide_terms(slide):
    """Основы значимых слов слайда с частотой и исходным написанием."""
    counts, shown = Counter(), {}
    for word in content_words(slide.text):
        key = stem(word)
        counts[key] += 1
        shown.setdefault(key, word)
    return counts, shown


def reading_share(spoken, slide_text):
    """Доля сказанных слов, которые идут подряд так же, как на слайде."""
    said, written = tokenize(spoken), tokenize(slide_text)
    if len(said) < READING_NGRAM or len(written) < READING_NGRAM:
        return 0
    grams = {tuple(written[i:i + READING_NGRAM]) for i in range(len(written) - READING_NGRAM + 1)}
    read = [False] * len(said)
    for i in range(len(said) - READING_NGRAM + 1):
        if tuple(said[i:i + READING_NGRAM]) in grams:
            for k in range(i, i + READING_NGRAM):
                read[k] = True
    return round(100 * sum(read) / len(said))


def align(similarity, positions, slides):
    """Привязка фраз к слайдам: слайды идут по порядку, сумма сходства наибольшая."""
    best, back = [], []
    for j, row in enumerate(similarity):
        scores, pointers = [], []
        running, running_at = -math.inf, 0
        for i in range(slides):
            if j == 0:
                previous, source = 0.0, i
            else:
                if best[j - 1][i] > running:
                    running, running_at = best[j - 1][i], i
                previous, source = running, running_at
            expected = i / (slides - 1) if slides > 1 else 0.0
            scores.append(previous + row[i] - PRIOR * abs(expected - positions[j]))
            pointers.append(source)
        best.append(scores)
        back.append(pointers)
    if not best:
        return []
    path = [max(range(slides), key=lambda i: best[-1][i])]
    for j in range(len(best) - 1, 0, -1):
        path.append(back[j][path[-1]])
    return path[::-1]


def pages(numbers):
    numbers = [str(n) for n in numbers]
    one, many, also, more = lang.text(("Слайд", "Слайды", "и", "и ещё"), ("Slide", "Slides", "and", "and"))
    if len(numbers) > MAX_LISTED:
        rest = len(numbers) - MAX_LISTED
        return f"{many} " + ", ".join(numbers[:MAX_LISTED]) + f" {more} {rest}" + lang.text("", " more")
    if len(numbers) == 1:
        return f"{one} {numbers[0]}"
    return f"{many} " + ", ".join(numbers[:-1]) + f" {also} " + numbers[-1]


def lexical_similarity(slides, segments):
    """Сходство фраз и слайдов по общим словам: строки соответствуют фразам, столбцы слайдам."""
    terms = [slide_terms(slide) for slide in slides]
    weight, scale = term_weights(terms, len(slides))
    spoken = [{stem(word) for word in content_words(segment["text"])} for segment in segments]
    return [[sum(weight[key] for key in said if key in counts) / scale for counts, _ in terms] for said in spoken]


def semantic_cosine(slides, segments, embedder):
    """Косинус между векторами фраз и слайдов: строки соответствуют фразам, столбцы слайдам."""
    import numpy as np

    if not slides or not segments:
        return np.zeros((len(segments), len(slides)), dtype="float32")
    said = embedder.encode([segment["text"] for segment in segments], kind="query")
    shown = embedder.encode([slide.text[:2000] or "пустой слайд" for slide in slides], kind="passage")
    return said @ shown.T


def standardize(cosine):
    """Отклонение от среднего по слайдам: какой слайд ближе к фразе, чем остальные. Сырой косинус для любых
    двух русских текстов лежит в узкой полосе, и для привязки нужна разница между слайдами, а не величина."""
    import numpy as np

    if cosine.size == 0:
        return cosine
    spread = cosine.std(axis=1, keepdims=True)
    return (cosine - cosine.mean(axis=1, keepdims=True)) / np.where(spread > 1e-6, spread, 1.0)


def semantic_similarity(slides, segments, embedder):
    return standardize(semantic_cosine(slides, segments, embedder))


def term_weights(terms, total):
    seen = Counter(key for counts, _ in terms for key in counts)
    weight = {key: math.log((total + 1) / (count + 0.5)) for key, count in seen.items()}
    return weight, (sum(weight.values()) / len(weight) if weight else 1.0)


def key_coverage(counts, weight, near):
    """Доля веса главных слов слайда, которые прозвучали. Возвращает None, если слов на слайде слишком мало."""
    # Распознаватель пишет русскую речь кириллицей, поэтому латинские надписи (код, названия) в речи не найти.
    # Они проверяются, только если русских слов на слайде почти нет.
    script = lang.own_script()
    native = [key for key in counts if script.search(key)]
    candidates = native if len(native) >= 3 else list(counts)
    key_terms = sorted(candidates, key=lambda key: -(weight[key] * (1 + math.log(counts[key]))))[:KEY_TERMS]
    full = sum(weight[key] for key in key_terms)
    if not full or len(key_terms) < 3:
        return None, key_terms
    return round(100 * sum(weight[key] for key in key_terms if key in near) / full), key_terms


def slide_status(coverage, reading, spoken, meaning=None):
    """Оценка слайда. meaning: средний косинус между слайдом и фразами, сказанными на нём."""
    if coverage is None:
        return "no_text"
    if spoken and reading >= READING_SHARE:
        return "partly"         # слайд зачитан: слова прозвучали, хотя ключевых среди них мало
    if not spoken:
        return "skipped"
    if coverage < SKIPPED_BELOW:
        # Общих слов почти нет, но по смыслу речь об этом слайде: докладчик пересказал его своими словами.
        return "retold" if meaning is not None and meaning >= RETOLD_MEANING else "skipped"
    return "partly" if coverage < 60 else "covered"


def by_timeline(segments, timeline, total):
    """Привязка по отметкам приложения: фраза относится к слайду, который был на экране бо́льшую часть её времени."""
    marks = sorted(({"page": int(m["page"]), "start": float(m["start"])} for m in timeline), key=lambda m: m["start"])
    assigned = []
    for segment in segments:
        shown = {}
        for index, mark in enumerate(marks):
            end = marks[index + 1]["start"] if index + 1 < len(marks) else math.inf
            shared = min(segment["end"], end) - max(segment["start"], mark["start"])
            if shared > 0:
                shown[mark["page"]] = shown.get(mark["page"], 0.0) + shared
        page = max(shown, key=shown.get) if shown else marks[0]["page"]
        assigned.append(min(max(page, 1), total) - 1)
    return assigned


def shown_seconds(timeline, duration, total):
    """Сколько секунд каждый слайд был на экране по отметкам приложения."""
    marks = sorted(({"page": int(m["page"]), "start": float(m["start"])} for m in timeline), key=lambda m: m["start"])
    seconds = [0.0] * total
    for index, mark in enumerate(marks):
        end = marks[index + 1]["start"] if index + 1 < len(marks) else duration
        if 1 <= mark["page"] <= total:
            seconds[mark["page"] - 1] += max(0.0, min(end, duration) - mark["start"])
    return seconds


def match_slides(slides, segments, duration, timeline=None, embedder=None):
    """Сводка по презентации: общая оценка, разбор каждого слайда и замечания.

    timeline: отметки приложения о смене слайдов [{"page": 2, "start": 14.2}]. С ними время на слайд точное,
    без них фразы привязываются к слайдам по словам и смыслу.
    """
    terms = [slide_terms(slide) for slide in slides]
    total = len(slides)
    weight, _ = term_weights(terms, total)
    spoken = [{stem(word) for word in content_words(segment["text"])} for segment in segments]
    meaning = None
    if embedder is not None and slides and segments:
        try:
            meaning = semantic_cosine(slides, segments, embedder)
        except Exception:
            log.exception("Смысловые векторы недоступны, слайды сопоставляются только по словам")
    timed = bool(timeline) and total > 0
    if timed:
        assigned = by_timeline(segments, timeline, total)
        shown = shown_seconds(timeline, duration, total)
    else:
        similarity = lexical_similarity(slides, segments)
        if meaning is not None:
            similarity = [[lex + MEANING_WEIGHT * float(sem) for lex, sem in zip(row, extra)]
                          for row, extra in zip(similarity, standardize(meaning))]
        positions = [((s["start"] + s["end"]) / 2) / duration if duration else 0.0 for s in segments]
        assigned = align(similarity, positions, total) if total else []

    items, read_words, all_words = [], 0, 0
    for index, slide in enumerate(slides):
        counts, shown_as = terms[index]
        own = [j for j, target in enumerate(assigned) if target == index]
        # Без отметок приложения граница между слайдами приблизительная, поэтому слова ищем и во фразах соседних слайдов.
        reach = 0 if timed else 1
        near = set().union(*[spoken[j] for j, target in enumerate(assigned) if abs(target - index) <= reach]) if assigned else set()
        coverage, key_terms = key_coverage(counts, weight, near)
        text = " ".join(segments[j]["text"] for j in own)
        said_count = len(tokenize(text))
        reading = reading_share(text, slide.text)
        read_words += reading * said_count
        all_words += said_count
        closeness = float(sum(meaning[j][index] for j in own) / len(own)) if meaning is not None and own else None
        status = slide_status(coverage, reading, bool(own), closeness)
        items.append({
            "page": slide.page,
            "title": slide.title[:80],
            "words": slide.words,
            "seconds": round(shown[index]) if timed else round(sum(segments[j]["end"] - segments[j]["start"] for j in own)),
            "coverage": coverage,
            "reading": reading,
            "missed": [shown_as[key] for key in key_terms if key not in near][:4] if status in ("skipped", "partly") else [],
            "status": status,
            "dense": getattr(slide, "typed_words", slide.words) > DENSE_WORDS,
            "small_text": slide.small_text >= SMALL_TEXT_SHARE,
        })

    scored = [item["coverage"] for item in items if item["coverage"] is not None]
    coverage = round(sum(scored) / len(scored)) if scored else None
    return {
        "pages": total,
        "coverage": coverage,
        "reading": round(read_words / all_words) if all_words else 0,
        "timed": timed,
        "items": items,
        "notes": build_notes(items, coverage),
    }


def build_notes(items, coverage=None):
    say = lang.text
    notes = []
    retold = sum(item["status"] == "retold" for item in items)
    if coverage is not None and coverage < UNRELATED and len(items) >= 3 and not retold:
        # Перечислять все слайды как пропущенные бессмысленно: скорее всего, приложен не тот файл.
        return [say("Речь почти не пересекается с презентацией. **Проверьте, тот ли файл вы приложили.**",
                    "The speech barely overlaps with the presentation. **Check that you attached the right file.**")]
    skipped = [item["page"] for item in items if item["status"] == "skipped"]
    if skipped:
        notes.append(pages(skipped) + say(
            ": то, что написано на слайде, в речи не прозвучало. **Расскажите о нём словами или уберите его из презентации.**",
            ": what is written on the slide was never said. **Talk about it or remove it from the deck.**"))
    read = [item["page"] for item in items if item["reading"] >= READING_SHARE and item["seconds"] >= 5]
    if read:
        notes.append(pages(read) + say(
            ": вы читали текст со слайда. **Оставьте на слайде тезисы, а подробности расскажите своими словами.**",
            ": you read the text off the slide. **Keep key points on the slide and give the details in your own words.**"))
    dense = [item["page"] for item in items if item["dense"]]
    if dense:
        notes.append(pages(dense) + say(
            f": больше {DENSE_WORDS} слов. Зритель не успевает читать и слушать одновременно. **Сократите текст или разбейте слайд на два.**",
            f": more than {DENSE_WORDS} words. The audience cannot read and listen at once. **Cut the text or split the slide in two.**"))
    small = [item["page"] for item in items if item["small_text"]]
    if small:
        notes.append(pages(small) + say(
            ": бо́льшая часть текста набрана мелко и с задних рядов не прочитается. **Увеличьте шрифт.**",
            ": most of the text is small and cannot be read from the back rows. **Use a larger font.**"))
    timed = sorted(item["seconds"] for item in items if item["seconds"] > 0)
    if len(timed) >= 3:
        median = timed[len(timed) // 2]
        long = [item["page"] for item in items if item["seconds"] > max(3 * median, 60)]
        if long:
            notes.append(pages(long) + say(
                ": на него ушло втрое больше времени, чем на остальные. **Проверьте, не стоит ли разделить его.**",
                ": it took three times longer than the others. **Consider splitting it.**"))
    if not notes and items:
        notes.append(say("Речь и слайды согласованы: каждый слайд раскрыт словами, текст не зачитывается.",
                         "The speech and the slides match: every slide is covered and none is read aloud."))
    return notes
