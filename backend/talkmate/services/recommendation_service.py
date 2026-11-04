"""Текстовые рекомендации по результатам оценки. Двойные звёздочки выделяют главное действие."""
from speech_analysis import lang

ADVICE = {
    "volume_quiet": (
        "**увеличить громкость** вашего голоса, чтобы слушателям было проще вас услышать и легче "
        "улавливать ту ценную информацию, которую вы передаете. Это позволит повысить эффективность "
        "восприятия вашего сообщения."
    ),
    "volume_loud": (
        "**говорить немного тише**: слишком громкая речь утомляет слушателей и звучит как давление. "
        "Оставьте громкость для мест, которые хотите подчеркнуть."
    ),
    "rate_fast": (
        "**замедлить темп** до {rate_slow:.0f}–{rate_fast:.0f} слов в минуту. Сейчас у вас {rate:.0f}: "
        "слушатели не успевают за мыслью. Делайте паузу после каждой законченной фразы."
    ),
    "rate_slow": (
        "**говорить чуть быстрее**: {rate:.0f} слов в минуту воспринимается как затянутая речь, "
        "комфортный темп лежит между {rate_slow:.0f} и {rate_fast:.0f}. Проговорите текст заранее, "
        "чтобы не подбирать слова на ходу."
    ),
    "monotone": (
        "**добавить интонации**: голос звучит на одной высоте, и важные мысли теряются. "
        "Повышайте тон на вопросах и ключевых словах, понижайте в конце законченной мысли."
    ),
    "fillers": (
        "**убрать слова-заполнители** ({examples}): в записи их {count}. Когда хочется сказать такое "
        "слово, сделайте короткую паузу и вдохните."
    ),
    "no_intro": (
        "**начинать со вступления**: в первых фразах скажите, о чём пойдёт речь и зачем это слушателю. "
        "Без этого аудитория первые полминуты пытается понять тему."
    ),
    "no_conclusion": (
        "**заканчивать выводом**: последней фразой повторите главную мысль или скажите, что слушателю сделать дальше. "
        "Сейчас выступление обрывается."
    ),
    "unclear": (
        "**говорить чётче**: часть слов прозвучала неразборчиво, чёткость записи {clarity:.0f}%. Проговаривайте "
        "окончания и не глотайте слоги, а в расшифровке посмотрите, какие слова подчёркнуты. На оценку влияют "
        "и шум вокруг, и расстояние до микрофона."
    ),
    "noisy": (
        "**записаться в тихом месте**: вокруг шумно, речь громче фона всего на {snr:.0f} дБ. Из-за этого часть слов "
        "распознана неуверенно, и оценки могли получиться строже, чем есть на самом деле. Закройте окно, отойдите от "
        "кондиционера и держите телефон в 20–30 см от рта."
    ),
    "emotion": (
        "**следить за настроением речи**: в голосе слышится {emotion}. Перед выступлением сделайте "
        "несколько медленных выдохов и начните с улыбки, тогда тон станет спокойнее."
    ),
}

ADVICE_EN = {
    "volume_quiet": (
        "**speak louder** so that listeners hear you easily and catch what you are saying. "
        "A quiet voice makes the audience work to follow you."
    ),
    "volume_loud": (
        "**speak a little more quietly**: a voice that is too loud tires the audience and sounds like pressure. "
        "Save the volume for the points you want to stress."
    ),
    "rate_fast": (
        "**slow down** to {rate_slow:.0f}–{rate_fast:.0f} words per minute. You are at {rate:.0f} now: "
        "listeners cannot keep up with the idea. Pause after each complete sentence."
    ),
    "rate_slow": (
        "**speak a little faster**: {rate:.0f} words per minute feels drawn out, "
        "a comfortable pace lies between {rate_slow:.0f} and {rate_fast:.0f}. Rehearse the text aloud beforehand "
        "so that you do not search for words as you go."
    ),
    "monotone": (
        "**add intonation**: your voice stays at one pitch and the important ideas get lost. "
        "Raise the pitch on questions and key words, lower it at the end of a complete thought."
    ),
    "fillers": (
        "**drop the filler words** ({examples}): there are {count} of them in the recording. When you feel one "
        "coming, take a short pause and breathe in."
    ),
    "no_intro": (
        "**start with an introduction**: in the first sentences say what the talk is about and why it matters to the listener. "
        "Without it the audience spends the first half minute working out the topic."
    ),
    "no_conclusion": (
        "**end with a conclusion**: use the last sentence to repeat the main idea or to say what the listener should do next. "
        "Right now the talk just stops."
    ),
    "unclear": (
        "**speak more clearly**: some words were hard to make out, the clarity of the recording is {clarity:.0f}%. Finish "
        "your word endings and do not swallow syllables, and check the transcript for the underlined words. Background noise "
        "and the distance to the microphone also affect this score."
    ),
    "noisy": (
        "**record in a quieter place**: there is background noise, your voice is only {snr:.0f} dB louder than it. Because "
        "of that some words were recognised with low confidence, and the scores may be stricter than they should be. Close "
        "the window, move away from the air conditioner and hold the phone 20–30 cm from your mouth."
    ),
    "emotion": (
        "**watch the mood of your voice**: it carries {emotion}. Before the talk breathe out slowly "
        "a few times and start with a smile, the tone will become calmer."
    ),
}

NEGATIVE_EMOTIONS = {"anger": "злость", "disgust": "отвращение", "fear": "страх", "sadness": "грусть"}
NEGATIVE_EMOTIONS_EN = {"anger": "anger", "disgust": "disgust", "fear": "fear", "sadness": "sadness"}


def find_issues(result, thresholds):
    issues = []
    if result.volume == "quiet":
        issues.append("volume_quiet")
    elif result.volume == "loud":
        issues.append("volume_loud")
    if result.speech_rate > thresholds["rate_fast"]:
        issues.append("rate_fast")
    elif 0 < result.speech_rate < thresholds["rate_slow"]:
        issues.append("rate_slow")
    if result.monotony == "monotone":
        issues.append("monotone")
    if result.num_fillers > thresholds["fillers_max"]:
        issues.append("fillers")
    structure = (getattr(result, "content", None) or {}).get("structure") or {}
    if structure.get("intro") is False:
        issues.append("no_intro")
    if structure.get("conclusion") is False:
        issues.append("no_conclusion")
    # В шумной записи низкая чёткость говорит об условиях, а не о дикции: советуем тишину вместо «говорить чётче».
    if getattr(result, "noise_level", None) == "noisy":
        issues.append("noisy")
    elif getattr(result, "clarity_level", None) == "unclear":
        issues.append("unclear")
    if result.emotion in NEGATIVE_EMOTIONS:
        issues.append("emotion")
    return issues


def build_recommendation(result, thresholds):
    """Возвращает (заголовок, текст) на языке интерфейса."""
    english = lang.ui() == "en"
    issues = find_issues(result, thresholds)
    quote = "“{}”" if english else "«{}»"
    # Примеры заполнителей берутся из языка речи: в английской записи это um и you know.
    defaults = ("um", "you know") if getattr(result, "language", "ru") == "en" else ("ну", "вот")
    params = {
        "rate": result.speech_rate,
        "rate_slow": thresholds["rate_slow"],
        "rate_fast": thresholds["rate_fast"],
        "count": result.num_fillers,
        "examples": ", ".join(quote.format(w) for w in (result.top_fillers or defaults)),
        "emotion": (NEGATIVE_EMOTIONS_EN if english else NEGATIVE_EMOTIONS).get(result.emotion, ""),
        "clarity": getattr(result, "clarity", None) or 0,
        "snr": getattr(result, "snr_db", None) or 0,
    }
    if not issues:
        if english:
            return (
                "Great talk!",
                "Pace, volume and intonation are within the norm and there are almost no filler words. **Lock in the result**: "
                "record the same talk again tomorrow and compare the charts in My progress.",
            )
        return (
            "Отличное выступление!",
            "Темп, громкость и интонации в норме, лишних слов почти нет. **Закрепите результат**: "
            "запишите то же выступление ещё раз завтра и сравните графики в разделе Stats.",
        )
    if english:
        title = "You are doing well!" if len(issues) <= 2 else "There is room to improve"
        openers = ["Next time try to ", "It is also worth trying to ", "Also try to ", "And finally, try to "]
    else:
        title = "У вас здорово получается!" if len(issues) <= 2 else "Есть над чем поработать"
        openers = ["В следующий раз попробуйте ", "Ещё стоит ", "Также постарайтесь ", "И наконец, попробуйте "]
    advice = ADVICE_EN if english else ADVICE
    parts = []
    for index, issue in enumerate(issues):
        opener = openers[min(index, len(openers) - 1)]
        parts.append(opener + advice[issue].format(**params))
    return title, "\n\n".join(parts)
