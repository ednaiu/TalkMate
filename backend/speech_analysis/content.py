"""Содержание выступления: основная мысль, ключевые слова и оценка структуры.

Основную мысль формулирует локальная модель пересказа (summarizer.py). Здесь лежит запасной способ
и всё остальное, что считается по расшифровке без моделей:
- запасная основная мысль выбирается из сказанного как самая содержательная фраза (метод Луна: фраза тем
  важнее, чем больше в ней слов, которые часто встречаются во всём выступлении);
- структура оценивается по трём признакам: вступление в начале, логические связки в основной части,
  заключение в конце.

Ограничение запасного способа: мысль не переформулируется, а цитируется. Если говорящий ни разу не
произнёс её одной фразой, выбранная цитата может быть неточной.
"""
import re
from collections import Counter

from . import lang
from .fillers import filler_spans
from .speed import tokenize

MIN_WORDS_FOR_STRUCTURE = 40      # на более короткой записи вступление и заключение искать бессмысленно
EDGE_SHARE = 0.25                 # доля текста, которая считается началом и концом выступления

STOPWORDS = set("""
и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по только ее мне было вот от меня еще нет о из
ему теперь когда даже ну вдруг ли если уже или ни быть был него до вас нибудь опять уж вам ведь там потом себя ничего ей может
они тут где есть надо ней для мы тебя их чем была сам чтоб без будто чего раз тоже себе под будет ж тогда кто этот того потому
этого какой совсем ним здесь этом один почти мой тем чтобы нее сейчас были куда зачем всех никогда можно при наконец два об
другой хоть после над больше тот через эти нас про всего них какая много разве три эту моя впрочем хорошо свою этой перед иногда
лучше чуть том нельзя такой им более всегда конечно всю между это эта весь очень просто также который которая которые которое
которых которого которой которым своей своего свои свой своем своих наш наша наше наши нашего нашей нашем наших ваш ваша ваше ваши тебе нам вами будут буду будем является
являются мой моя мое мои моего моей моему моим моих мою твой твоя должен должна должны должно хочу хотим хотел хотела
знаю знаем могу можем можете типа короче значит собственно этот эти этих этим того тех тому такие такая такое таких так вообще самом деле
""".split())

STOPWORDS_EN = set("""
a an the and or but if so of in on at to for from by with about into over after before under between through during without within
is are was were be been being am do does did done have has had having will would shall should can could may might must
i you he she it we they me him her us them my your his its our their mine yours this that these those there here
what which who whom whose when where why how not no nor only just very too also than then now as up down out off again
all any both each few more most other some such own same once because while until against further
im ive id ill youre youve dont doesnt didnt cant couldnt wont wouldnt isnt arent wasnt werent thats theres lets
going get got make made say said one two three thing things really quite
""".split())

INTRO_MARKERS_EN = [
    r"\bgood (morning|afternoon|evening)\b", r"\bhello\b", r"\bhi\b", r"\bmy name is\b", r"\btoday (i|we)\b",
    r"\bi (will|am going to|would like to|want to) (talk|tell|speak|present|share|show|discuss)", r"\blet me (introduce|start|begin)\b",
    r"\bwelcome\b", r"\bladies and gentlemen\b", r"\bcolleagues\b", r"\bthis (talk|presentation) is about\b", r"\bthe topic of\b",
    r"\blet us (start|begin)\b", r"\bi am here to\b",
]
CONCLUSION_MARKERS_EN = [
    r"\bin conclusion\b", r"\bto conclude\b", r"\bto sum up\b", r"\bin summary\b", r"\bto summarize\b", r"\bfinally\b",
    r"\boverall\b", r"\bthank you\b", r"\bthanks\b", r"\bquestions\b", r"\bthe (main|key) (point|takeaway)\b", r"\bremember\b",
    r"\bthat is all\b", r"\bto wrap up\b", r"\bthe takeaway\b",
]
THESIS_MARKERS_EN = [
    r"\bi will talk about\b", r"\bi want to (show|talk)\b", r"\bthe main (idea|point)\b", r"\bin conclusion\b", r"\bthe key\b",
    r"\bthis (talk|presentation)\b", r"\bto sum up\b",
]
LINK_MARKERS_EN = [
    r"\bfirst(ly)?\b", r"\bsecond(ly)?\b", r"\bthird(ly)?\b", r"\bfor example\b", r"\bfor instance\b", r"\bbecause\b", r"\btherefore\b",
    r"\bhowever\b", r"\bmoreover\b", r"\bin addition\b", r"\bon the one hand\b", r"\bon the other hand\b", r"\bnext\b",
    r"\bas a result\b", r"\bin other words\b", r"\bthat is why\b", r"\bthus\b", r"\bconsequently\b", r"\bin contrast\b",
]

INTRO_MARKERS = [
    r"\bздравствуйте\b", r"\bдобрый (день|вечер)\b", r"\bдоброе утро\b", r"\bпривет\b", r"\bприветствую\b", r"\bменя зовут\b",
    r"\bсегодня (я|мы)\b", r"\bя (расскажу|хочу рассказать|хотел бы|хотела бы|хочу поговорить|хочу поделиться)\b",
    r"\b(мы )?поговорим\b", r"\bтема (моего|нашего|сегодняшнего)\b", r"\bречь пойд[её]т\b", r"\bмой доклад\b", r"\bмо[её] выступлени",
    r"\bпредставлю\b", r"\bначн[её]м\b", r"\bначну с\b", r"\bуважаемые\b", r"\bколлеги\b", r"\bдрузья\b",
]
CONCLUSION_MARKERS = [
    r"\bитак\b", r"\bв заключени[еи]\b", r"\bподводя итог", r"\bподвед[её]м итог", r"\bтаким образом\b", r"\bв итоге\b", r"\bв завершени[еи]\b",
    r"\bрезюмиру", r"\bвывод", r"\bнапоследок\b", r"\bспасибо\b", r"\bблагодарю\b", r"\bвопросы\b", r"\bна этом (вс[её]|у меня вс[её])\b",
    r"\bглавное\b", r"\bзапомните\b", r"\bпризываю\b",
]
# Фразы, которыми говорящий сам объявляет тему или главный вывод: у такой фразы больше шансов быть основной мыслью.
THESIS_MARKERS = [
    r"\bрасскажу\b", r"\bхочу рассказать\b", r"\bпоговорим\b", r"\bречь пойдет\b", r"\bтема\b", r"\bглавн(ое|ая мысль)\b",
    r"\bсуть\b", r"\bидея\b", r"\bвывод\b", r"\bитак\b", r"\bтаким образом\b", r"\bхочу (показать|доказать|убедить)\b",
]
LINK_MARKERS = [
    r"\bво-первых\b", r"\bво-вторых\b", r"\bв-третьих\b", r"\bнапример\b", r"\bк примеру\b", r"\bпотому что\b", r"\bпоэтому\b",
    r"\bследовательно\b", r"\bкроме того\b", r"\bболее того\b", r"\bс одной стороны\b", r"\bс другой стороны\b", r"\bоднако\b",
    r"\bзатем\b", r"\bдалее\b", r"\bнаконец\b", r"\bв результате\b", r"\bто есть\b", r"\bиными словами\b", r"\bпри этом\b",
    r"\bв отличие\b", r"\bпервое\b", r"\bвторое\b", r"\bтретье\b", r"\bважно\b", r"\bдело в том\b", r"\bименно поэтому\b",
]


def split_sentences(text):
    parts = re.split(r"(?<=[.!?…])\s+", (text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def stem(word):
    """Грубая основа слова: первые пять букв. Склеивает формы «выступление», «выступления», «выступлений»."""
    return word[:5] if len(word) > 5 else word


def content_words(text):
    """Значимые слова: без служебных, коротких, числовых и заполнителей."""
    fillers = {text[start:end].lower().replace("ё", "е") for start, end, _ in filler_spans(text)}
    stopwords = lang.rule(STOPWORDS, STOPWORDS_EN)
    return [w for w in tokenize(text) if len(w) > 2 and w not in stopwords and w not in fillers and not w.isdigit()]


def strip_fillers(sentence):
    """Фраза без слов-заполнителей: основную мысль показываем в чистом виде."""
    spans = filler_spans(sentence)
    if not spans:
        return sentence
    pieces, position = [], 0
    for start, end, _ in spans:
        pieces.append(sentence[position:start])
        position = end
    pieces.append(sentence[position:])
    cleaned = "".join(pieces)
    cleaned = re.sub(r"\s*,(\s*,)+", ",", cleaned)              # «, ,» после удалённого слова
    cleaned = re.sub(r"\s+([,.!?…])", r"\1", cleaned)
    cleaned = re.sub(r",\s*([.!?…])", r"\1", cleaned)           # запятая перед точкой после удалённого слова
    cleaned = re.sub(r"^[\s,–—-]+", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned[:1].upper() + cleaned[1:] if cleaned else sentence


MAX_IDEA_WORDS = 28


def clauses(sentence):
    """Слишком длинная фраза по частям. Распознаватель иногда ставит запятые вместо точек, и «фразой» оказывается
    полвыступления; такая основная мысль ничего не сообщает."""
    if len(tokenize(sentence)) <= MAX_IDEA_WORDS:
        return [sentence]
    parts, current = [], ""
    for piece in re.split(r",\s+", sentence):
        current = f"{current}, {piece}" if current else piece
        if len(tokenize(current)) >= 7:
            parts.append(current)
            current = ""
    if current:
        if parts:
            parts[-1] = f"{parts[-1]}, {current}"
        else:
            parts.append(current)
    return [part[:1].upper() + part[1:] + ("" if part[-1] in ".!?…" else ".") for part in parts]


def main_idea(text):
    """Самая содержательная фраза выступления и ключевые слова. Возвращает (фраза или None, [слова])."""
    sentences = [part for sentence in split_sentences(text) for part in clauses(sentence)]
    words = content_words(text)
    if len(words) < 4:
        return None, []
    frequency = Counter(stem(w) for w in words)

    forms = {}
    for w in words:
        forms.setdefault(stem(w), Counter())[w] += 1
    keywords = [forms[s].most_common(1)[0][0] for s, n in frequency.most_common(8) if n >= 2][:5]

    def pick(min_words):
        best, best_score = None, 0.0
        for index, sentence in enumerate(sentences):
            own = [stem(w) for w in content_words(sentence)]
            if len(own) < min_words:
                continue
            # Вес фразы: сумма частот её значимых слов. Деление на длину в степени 0,35 не даёт длинным фразам
            # побеждать автоматически, но и не отдаёт победу обрывкам из трёх слов.
            score = sum(frequency[s] for s in set(own)) / (len(own) ** 0.35)
            if _count(lang.rule(THESIS_MARKERS, THESIS_MARKERS_EN), sentence.lower().replace("ё", "е")):
                score *= 1.4         # говорящий сам сказал «сегодня я расскажу о…» или «итак, …»
            if score > best_score:
                best, best_score = sentence, score
        return best

    best = pick(4) or pick(3)
    return (strip_fillers(best) if best else None), keywords


def _count(patterns, text):
    return sum(len(re.findall(pattern, text)) for pattern in patterns)


def structure(text):
    """Оценка структуры: есть ли вступление, связки в основной части и заключение."""
    lowered = (text or "").lower().replace("ё", "е")
    words = tokenize(text)
    if len(words) < MIN_WORDS_FOR_STRUCTURE:
        return {"level": "short", "intro": None, "links": None, "conclusion": None,
                "summary": lang.text("Запись слишком короткая, чтобы оценить структуру: нужно хотя бы 40 слов.",
                                     "The recording is too short to assess its structure: at least 40 words are needed.")}
    edge = max(1, int(len(lowered) * EDGE_SHARE))
    patterns_intro = [p.replace("ё", "е") for p in lang.rule(INTRO_MARKERS, INTRO_MARKERS_EN)]
    patterns_end = [p.replace("ё", "е") for p in lang.rule(CONCLUSION_MARKERS, CONCLUSION_MARKERS_EN)]
    intro = _count(patterns_intro, lowered[:edge]) > 0
    conclusion = _count(patterns_end, lowered[-edge:]) > 0
    links = _count(lang.rule(LINK_MARKERS, LINK_MARKERS_EN), lowered)
    connected = links >= 2

    found = sum([intro, connected, conclusion])
    level = {3: "good", 2: "partial"}.get(found, "weak")
    notes = []
    example = lang.rule("во-первых, поэтому", "first, therefore")
    if lang.ui() == "en":
        notes.append("there is an introduction" if intro else "no introduction: the listener is not told what the talk is about")
        notes.append(f"linking phrases: {links}" if connected else f"few links between ideas (such as {example})")
        notes.append("there is a conclusion" if conclusion else "no conclusion: the talk stops without a takeaway")
    else:
        notes.append("вступление есть" if intro else "вступления нет: слушателю не сказали, о чём пойдёт речь")
        notes.append(f"логических связок: {links}" if connected else f"мало связок между мыслями (например, {example})")
        notes.append("заключение есть" if conclusion else "заключения нет: выступление обрывается без вывода")
    return {"level": level, "intro": intro, "links": links, "conclusion": conclusion, "summary": "; ".join(notes).capitalize() + "."}


def analyze_content(text, summary=None):
    """summary: пересказ от модели (speech_analysis.summarizer). Без него основной мыслью служит цитата."""
    idea, keywords = main_idea(text)
    return {
        "main_idea": summary or idea,
        # model: мысль сформулирована моделью пересказа; quote: выбрана фраза из самой речи.
        "main_idea_source": "model" if summary else ("quote" if idea else None),
        "keywords": keywords,
        "structure": structure(text),
    }
